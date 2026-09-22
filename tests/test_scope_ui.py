from pathlib import Path
import subprocess
import unittest


class StaticUiStartupSmokeTests(unittest.TestCase):
    def test_app_initializes_scope_state_with_dom_stub(self):
        root = Path(__file__).resolve().parents[1]
        stub = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
function node() {
  const n = {hidden:false,textContent:"",value:"",disabled:false,open:false,style:{setProperty(){}},classList:{toggle(){},add(){},remove(){}},childNodes:[],children:[],firstChild:{nodeType:3,textContent:""},dataset:{},parentElement:{firstChild:{nodeType:3,textContent:""}},
    addEventListener(){},removeEventListener(){},setAttribute(){},getAttribute(){return ""},append(){},appendChild(){},replaceChildren(){this.childNodes=[]},querySelector(){return node()},querySelectorAll(){return []},matches(){return false},focus(){},showModal(){this.open=true},close(){this.open=false}};
  return n;
}
const ids = new Map();
const document = {getElementById(id){if(!ids.has(id)) ids.set(id,node()); return ids.get(id)},querySelector(){return node()},querySelectorAll(){return []},createElement(){return node()},createElementNS(){return node()},addEventListener(){},body:node(),documentElement:node()};
const response = (data) => ({ok:true,json:async()=>data});
const context = {console,document,window:null,URL,URLSearchParams,Node:{TEXT_NODE:3},setTimeout,clearTimeout,setInterval,clearInterval,requestAnimationFrame:(fn)=>{fn();return 1},cancelAnimationFrame(){},localStorage:{getItem(){return null},setItem(){}},fetch:async(path)=> path==="/api/state"?response({runs:[],csrf_token:"stub"}):path==="/api/trash"?response({trash:[]}):path==="/api/auth/status"?response({available:false,authenticated:false}):response({}),ResizeObserver:class{observe(){}},__DEEPANALYZE_EXPORT__:null};
context.window=context; context.window.addEventListener=()=>{};
let failed=null; process.on("uncaughtException", (e)=>{failed=e});
vm.runInNewContext(source, context, {filename:"app.js"});
setTimeout(()=>{if(failed){console.error(failed.stack);process.exit(1)} process.exit(0)},80);
"""
        result = subprocess.run(["node", "-e", stub, str(root / "src/deepanalyze/static/app.js")], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
