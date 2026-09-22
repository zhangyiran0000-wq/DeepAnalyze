/* Pure chronology/lane planning for the research map. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.DeepAnalyzeLayout = api;
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";
  const list = (value) => Array.isArray(value) ? value : value == null ? [] : [value];
  const idOf = (item) => item && item.id != null ? String(item.id) : null;
  const yearOf = (node) => { const raw = node && (node.year != null ? node.year : String(node.date || "").slice(0, 4)); const year = Number(raw); return Number.isInteger(year) && year >= 1900 && year < 2200 ? year : null; };
  const primaryGroups = (nodes, groups) => { const known = new Set(groups.map(idOf)); const primary = new Map(); for (const node of nodes) { const group = list(node.group_ids).map(String).find((id) => known.has(id)); primary.set(String(node.id), group || "__ungrouped"); } return primary; };
  const supportedDependency = (edge) => { const kind = String(edge && (edge.kind || edge.type || "")).toLowerCase(); const status = String(edge && (edge.status || "")).toLowerCase(); return status === "supported" && (kind === "addresses" || kind === "builds_on"); };
  const nodeSort = (a, b, nodes) => { const left = nodes.get(a) || {}, right = nodes.get(b) || {}; return String(left.date || "").localeCompare(String(right.date || "")) || String(a).localeCompare(String(b)); };

  function plan(snapshot, inputGroups, layoutOptions) {
    const source = snapshot || {};
    const nodes = list(source.nodes).filter((node) => idOf(node) != null);
    const groups = list(inputGroups == null ? source.groups : inputGroups).filter((group) => idOf(group) != null).map((group) => ({ ...group, id: String(group.id) }));
    const hasUngrouped = nodes.some((node) => !groups.some((group) => list(node.group_ids).map(String).includes(group.id)));
    if ((hasUngrouped || !groups.length) && !groups.some((group) => group.id === "__ungrouped")) groups.push({ id: "__ungrouped", label: "Emerging connections" });
    const primary = primaryGroups(nodes, groups), byId = new Map(nodes.map((node) => [String(node.id), node]));
    const years = [...new Set(nodes.map(yearOf))].sort((a, b) => a === null ? 1 : b === null ? -1 : a - b);
    const rows = years.map((year) => ({ year, cells: Object.fromEntries(groups.map((group) => [group.id, []])) }));
    const rowByYear = new Map(rows.map((row) => [row.year, row]));
    const dependencies = list(source.edges).filter(supportedDependency).map((edge) => ({ source: String(edge.source), target: String(edge.target) })).filter((edge) => byId.has(edge.source) && byId.has(edge.target));
    for (const group of groups) for (const year of years) {
      const members = nodes.filter((node) => yearOf(node) === year && primary.get(String(node.id)) === group.id); if (!members.length) continue;
      const memberIds = new Set(members.map((node) => String(node.id))), levels = new Map(members.map((node) => [String(node.id), 0]));
      const dependencyNodes = new Set(), adjacency = new Map(members.map((node) => [String(node.id), []])), indegree = new Map(members.map((node) => [String(node.id), 0]));
      for (const edge of dependencies.filter((item) => memberIds.has(item.source) && memberIds.has(item.target))) { dependencyNodes.add(edge.source); dependencyNodes.add(edge.target); adjacency.get(edge.source).push(edge.target); indegree.set(edge.target, indegree.get(edge.target) + 1); }
      const queue = members.map((node) => String(node.id)).filter((id) => dependencyNodes.has(id) && indegree.get(id) === 0).sort((a, b) => nodeSort(a, b, byId));
      while (queue.length) { const id = queue.shift(); for (const target of adjacency.get(id).sort((a, b) => nodeSort(a, b, byId))) { levels.set(target, Math.max(levels.get(target), levels.get(id) + 1)); indegree.set(target, indegree.get(target) - 1); if (indegree.get(target) === 0) queue.push(target); } queue.sort((a, b) => nodeSort(a, b, byId)); }
      for (const id of dependencyNodes) if (!levels.has(id)) levels.set(id, 0);
      // Same-year non-rejected links also get deterministic staggered subrows. This
      // separates connected peers without changing chronology or edge semantics.
      const sameYearLinked = new Set(), sameYearAdj = new Map(members.map((node)=>[String(node.id),new Set()]));
      for (const edge of list(source.edges)) {
        if (String(edge.status || "").toLowerCase() === "rejected") continue;
        const sourceId=String(edge.source), targetId=String(edge.target);
        if (!memberIds.has(sourceId) || !memberIds.has(targetId)) continue;
        if (yearOf(byId.get(sourceId)) !== year || yearOf(byId.get(targetId)) !== year) continue;
        sameYearLinked.add(sourceId); sameYearLinked.add(targetId); sameYearAdj.get(sourceId).add(targetId); sameYearAdj.get(targetId).add(sourceId);
      }
      // Greedy coloring separates linked peers where supported levels are not fixed;
      // this is a layout offset only and does not alter chronology or semantic depth.
      const staggered = members.filter((node) => sameYearLinked.has(String(node.id)) && !dependencyNodes.has(String(node.id))).sort((a,b)=>nodeSort(String(a.id),String(b.id),byId));
      const assigned = new Map();
      for (const node of staggered) { const id=String(node.id), used=new Set([...sameYearAdj.get(id)].map((neighbor)=>assigned.get(neighbor)).filter((value)=>value!=null)); let level=0; while(used.has(level)) level++; assigned.set(id,level); levels.set(id,level); }
      const ordered = [], maxLevel = Math.max(0, ...levels.values());
      for (let level = 0; level <= maxLevel; level++) { const batch = [...levels].filter(([, value]) => value === level).map(([id]) => id).sort((a, b) => nodeSort(a, b, byId)); if (batch.length) ordered.push(batch); }
      rowByYear.get(year).cells[group.id] = ordered;
    }
    const rawColumns = Object.fromEntries(groups.map((group) => [group.id, Math.max(1, ...rows.map((row) => Math.max(0, ...(row.cells[group.id] || []).map((cell) => cell.length), 0)))]));
    const optionValue = typeof layoutOptions === "number" ? layoutOptions : layoutOptions && layoutOptions.availableWidth;
    const availableWidth = Number.isFinite(Number(optionValue)) && Number(optionValue) > 0 ? Number(optionValue) : null;
    const cardWidth = layoutOptions && Number.isFinite(Number(layoutOptions.minCardWidth)) ? Math.max(180, Number(layoutOptions.minCardWidth)) : 200;
    const gap = layoutOptions && Number.isFinite(Number(layoutOptions.gap)) ? Math.max(0, Number(layoutOptions.gap)) : 16;
    const capacities = {};
    if (availableWidth == null) for (const group of groups) capacities[group.id] = Math.min(rawColumns[group.id], 3);
    else {
      const totalColumns = Math.max(groups.length, Math.floor((availableWidth + gap) / (cardWidth + gap))); for (const group of groups) capacities[group.id] = 1;
      let remaining = Math.max(0, totalColumns - groups.length);
      while (remaining) { const candidate = groups.filter((group) => capacities[group.id] < rawColumns[group.id]).sort((a, b) => (rawColumns[b.id] - capacities[b.id]) - (rawColumns[a.id] - capacities[a.id]) || groups.indexOf(a) - groups.indexOf(b))[0]; if (!candidate) break; capacities[candidate.id] += 1; remaining -= 1; }
    }
    for (const row of rows) for (const group of groups) { const width = capacities[group.id]; row.cells[group.id] = (row.cells[group.id] || []).flatMap((cell) => { const chunks = []; for (let i = 0; i < cell.length; i += width) chunks.push(cell.slice(i, i + width)); return chunks; }); }
    const outputGroups = groups.map((group) => { const columns = Math.max(1, ...rows.map((row) => Math.max(0, ...(row.cells[group.id] || []).map((cell) => cell.length), 0))); return { ...group, columns, width: availableWidth == null ? columns * 264 : columns * cardWidth + Math.max(0, columns - 1) * gap }; });
    // Use otherwise empty horizontal space for curve clearance around cards.
    const spare=availableWidth == null ? 0 : Math.max(0,availableWidth-outputGroups.reduce((sum,g)=>sum+g.width,0));
    outputGroups.forEach(g=>{g.width+=Math.min(96,spare/Math.max(1,outputGroups.length));});
    const offsets = {}, positions = new Map();
    rows.forEach((row) => groups.forEach((group, gi) => (row.cells[group.id] || []).forEach((ids) => ids.forEach((id, col) => positions.set(id, gi + (col + .5) / capacities[group.id])))));
    const neighbors = new Map(nodes.map((n) => [String(n.id), []]));
    for (const edge of list(source.edges)) if (edge.status !== "rejected" && neighbors.has(String(edge.source)) && neighbors.has(String(edge.target))) {
      neighbors.get(String(edge.source)).push(String(edge.target)); neighbors.get(String(edge.target)).push(String(edge.source));
    }
    const barycenter = (id) => { const peers = neighbors.get(id).filter((peer) => positions.has(peer)); return peers.length ? peers.reduce((sum, peer) => sum + positions.get(peer), 0) / peers.length : positions.get(id); };
    for (const row of rows) groups.forEach((group, gi) => (row.cells[group.id] || []).forEach((ids) => {
      ids.sort((a, b) => barycenter(a) - barycenter(b) || nodeSort(a, b, byId));
      ids.forEach((id, col) => { offsets[id] = ((col + gi) % 3) * 28; });
    }));
    return { groups: outputGroups, years, rows, availableWidth, cardWidth, gap, offsets };
  }
  function segmentHits(a, b, rect, pad = 3) {
    // Clip a segment against the card's interior (also works for sampled curves).
    const bounds=[[rect.left-pad,rect.right+pad],[rect.top-pad,rect.bottom+pad]];
    let lo=0,hi=1;
    for(let axis=0;axis<2;axis++){
      const d=b[axis]-a[axis], [min,max]=bounds[axis];
      if(Math.abs(d)<1e-9){if(a[axis]<=min || a[axis]>=max)return false;continue;}
      const t1=(min-a[axis])/d,t2=(max-a[axis])/d;
      lo=Math.max(lo,Math.min(t1,t2));hi=Math.min(hi,Math.max(t1,t2));
      if(lo>=hi)return false;
    }
    return hi>0 && lo<1;
  }

  function routeEdge(source, target, rectangles, options = {}) {
    const width=options.width || Math.max(...rectangles.map(r=>r.right))+48;
    const height=options.height || Math.max(...rectangles.map(r=>r.bottom))+48;
    const clampX=x=>Math.max(5,Math.min(width-5,x)), clampY=y=>Math.max(5,Math.min(height-5,y));
    const frac=(slot,count)=>(slot+1)/(count+1);
    const sf=frac(options.sourceSlot||0,options.sourceCount||1),tf=frac(options.targetSlot||0,options.targetCount||1);
    const sx=source.left+14+(source.right-source.left-28)*sf;
    const tx=target.left+14+(target.right-target.left-28)*tf;
    const start=[sx,source.bottom],end=[tx,target.top],dy=end[1]-start[1];
    const obstacles=rectangles.filter(r=>r.id!==source.id && r.id!==target.id);
    const tracks=options.usedTracks || new Map();
    let best=null;
    const sample=curves=>{
      const points=[curves[0][0]];
      for(const [a,b,c,d] of curves){
        const length=Math.hypot(b[0]-a[0],b[1]-a[1])+Math.hypot(c[0]-b[0],c[1]-b[1])+Math.hypot(d[0]-c[0],d[1]-c[1]);
        const steps=Math.min(240,Math.max(12,Math.ceil(length/12)));
        for(let i=1;i<=steps;i++){const t=i/steps,u=1-t;points.push([u*u*u*a[0]+3*u*u*t*b[0]+3*u*t*t*c[0]+t*t*t*d[0],u*u*u*a[1]+3*u*u*t*b[1]+3*u*t*t*c[1]+t*t*t*d[1]]);}
      }
      return points;
    };
    const assess=curves=>{
      const points=sample(curves),minX=Math.min(...points.map(p=>p[0])),maxX=Math.max(...points.map(p=>p[0]));
      const minY=Math.min(...points.map(p=>p[1])),maxY=Math.max(...points.map(p=>p[1]));
      let collisions=0;
      for(const rect of [...obstacles,source,target]){
        if(rect.right<minX || rect.left>maxX || rect.bottom<minY || rect.top>maxY)continue;
        if(points.slice(1).some((b,i)=>segmentHits(points[i],b,rect,rect===source||rect===target ? -1 : 3)))collisions++;
      }
      if(best && collisions>best.collisions)return;
      let length=0,crowding=0;
      for(let i=1;i<points.length;i++){
        const p=points[i],a=points[i-1];length+=Math.hypot(p[0]-a[0],p[1]-a[1]);
        if((tracks.get(Math.round(p[1]/16))||[]).some(x=>Math.abs(x-p[0])<8))crowding++;
      }
      const score=collisions*10000000+length+crowding*32;
      if(!best || score<best.score)best={curves,points,collisions,score};
    };
    // Nearby transitions use a gentle bow rather than a vertical shared trunk.
    if(dy>12){const h=Math.max(14,Math.min(100,dy*.4));for(const bend of [-46,-22,22,46])
      assess([[start,[clampX(sx+bend),start[1]+h],[clampX(tx+bend),end[1]-h],end]]);}
    // Longer connections leave and arrive at distinct side ports. Three cubic
    // arcs fan out through a free corridor; the middle arc bows too, so parallel
    // links never collapse into an orthogonal bus.
    const sy=source.top+18+(source.bottom-source.top-36)*sf;
    const ty=target.top+18+(target.bottom-target.top-36)*tf;
    const direction=ty>=sy?1:-1,shoulder=Math.min(64,Math.abs(ty-sy)*.22);
    const corridors=[8,width-8,...rectangles.flatMap(r=>[r.left-14,r.right+14])];
    const unique=[...new Set(corridors.map(x=>Math.round(clampX(x))))];
    for(const rawX of unique){
      const x=clampX(rawX+((options.index||0)%5-2)*3);
      const spanObstacles=obstacles.filter(r=>r.bottom>Math.min(sy,ty) && r.top<Math.max(sy,ty));
      const leftBound=Math.max(5,...spanObstacles.filter(r=>r.right<x).map(r=>r.right+5));
      const rightBound=Math.min(width-5,...spanObstacles.filter(r=>r.left>x).map(r=>r.left-5));
      const bows=[-Math.max(4,Math.min(110,(x-leftBound)*.85)),Math.max(4,Math.min(110,(rightBound-x)*.85))];
      for(const bow of bows)for(const sourceSide of [true,false])for(const targetSide of [true,false]){
        const a=sourceSide ? [x<(source.left+source.right)/2 ? source.left : source.right,sy] : start;
        const d=targetSide ? [x<(target.left+target.right)/2 ? target.left : target.right,ty] : end;
        const b=[x,clampY(sourceSide ? sy+direction*shoulder : source.bottom+18)];
        const c=[x,clampY(targetSide ? ty-direction*shoulder : target.top-18)];
        const first=sourceSide ? [a,[x,sy],[x,b[1]-direction*shoulder*.35],b] : [a,[sx,b[1]],[x,a[1]],b];
        const last=targetSide ? [c,[x,c[1]+direction*shoulder*.35],[x,ty],d] : [c,[x,d[1]],[tx,c[1]],d];
        const mid=(c[1]-b[1])*.36,bulge=clampX(x+bow);
        assess([first,[b,[bulge,b[1]+mid],[bulge,c[1]-mid],c],last]);
      }
    }
    if(best.collisions){
      // A cross-column connection may need a different departure and arrival
      // corridor. Join them with an S-curve through an inter-row gap.
      const outY=clampY(source.bottom+18),inY=clampY(target.top-18),dir=inY>=outY?1:-1;
      const exits=[source.left-12,source.right+12,8,width-8].map(clampX);
      const entries=[target.left-12,target.right+12,8,width-8].map(clampX);
      const bridges=[...new Set(rectangles.flatMap(r=>[r.top-13,r.bottom+13]))]
        .filter(y=>y>Math.min(outY,inY)+20 && y<Math.max(outY,inY)-20);
      for(const x of exits)for(const z of entries)for(const y of bridges){
        const a=[x,outY],b=[x,y-dir*8],c=[z,y+dir*8],d=[z,inY];
        const bow=x<width/2?-4:4,bow2=z<width/2?-4:4;
        const h=(b[1]-a[1])*.36,k=(d[1]-c[1])*.36;
        assess([[start,[sx,outY],[x,start[1]],a],
          [a,[clampX(x+bow),a[1]+h],[clampX(x+bow),b[1]-h],b],
          [b,[x,y],[z,y],c],
          [c,[clampX(z+bow2),c[1]+k],[clampX(z+bow2),d[1]-k],d],
          [d,[z,end[1]],[tx,inY],end]]);
      }
    }
    // Store sampled occupancy so later edges prefer visibly separated arcs.
    for(const [x,y] of best.points){const key=Math.round(y/16);if(!tracks.has(key))tracks.set(key,[]);const bucket=tracks.get(key);if(!bucket.some(old=>Math.abs(old-x)<2))bucket.push(x);}
    const path='M '+best.curves[0][0].join(' ')+' '+best.curves.map(c=>'C '+c.slice(1).map(p=>p.join(' ')).join(' ')).join(' ');
    return {path,points:best.points,collisions:best.collisions};
  }
  return { plan, yearOf, isSupportedDependency: supportedDependency, routeEdge, segmentHits };

});