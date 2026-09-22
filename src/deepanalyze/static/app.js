/* DeepAnalyze local research workspace. No credentials are stored by this UI. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const exported = window.__DEEPANALYZE_EXPORT__ || null;
  const translations = {
    zh: {"Language":"语言","Local workspace":"本地工作区","Connect Codex":"连接 Codex","START AN EXPLORATION":"开始探索","One paper. A deeper question.":"一篇论文，一个更深的问题。","Start with a title, DOI, or arXiv link.":"从标题、DOI 或 arXiv 链接开始。","Which paper do you want to trace?":"你想追踪哪篇论文？","Exploration budget":"探索预算","Rounds":"轮次","Read / round":"每轮阅读","Candidates / round":"每轮候选","Model calls":"模型调用","Time limit (min)":"时间限制（分钟）","optional":"可选","Hard limits on work, not a guarantee of research completeness.":"工作硬限制，不保证研究完整性。","Trace this paper":"追踪这篇论文","Explore an illustrative demo":"查看示例演示","Demo uses synthetic examples. No login or model calls.":"演示使用合成示例，不需要登录或模型调用。","YOUR EXPLORATIONS":"你的探索","Your research history will appear here.":"你的研究历史会显示在这里。","Trash":"回收站","Deleted explorations can be restored here.":"已删除的探索可在这里恢复。","Restore":"恢复","Delete":"删除","THE RESEARCH LANDSCAPE":"研究全景","Follow the underlying logic.":"追踪背后的逻辑。","From one paper to the problems that shaped what came next.":"从一篇论文，到塑造后续工作的那些问题。","RESEARCH EVOLUTION":"研究演进","BRANCHED EXPLORATION":"分支探索","Stop exploration":"停止探索","Go to running exploration":"前往运行中的探索","Stop running":"停止运行","Branch from here ↗":"从这里创建分支 ↗","Export HTML ↓":"导出 HTML ↓","Saved snapshot":"已保存快照","Supported connection":"有依据的连接","Hypothesis":"假设","Fit":"适配","Background":"补充背景","SEED":"种子","YEAR":"年份","Undated":"未标日期","papers":"篇论文","connections":"个连接","depth":"深度","This iteration has no included papers. Review its gaps and activity.":"本轮没有纳入论文，请检查缺口和活动记录。","Context role":"背景角色","MODEL CONNECTION":"模型连接","Connect your Codex runtime":"连接 Codex 运行时","START WITH CURIOSITY":"从好奇开始","PAPER DETAIL":"论文详情","CONNECTION DETAIL":"连接详情","EXPLORATION NOTES":"探索笔记","Problem addressed":"解决的问题","Change in mechanism":"机制变化","Results and consequences":"结果与影响","Limitations":"局限","Assumptions & conditions":"假设与条件","Uncertainty":"不确定性","Connected work":"关联工作","Evidence":"证据","Illustrative source material":"示例来源材料","Source evidence":"来源证据","Unresolved gaps":"未解决的问题","Changes in this iteration":"本轮变化","Research scope":"研究范围","How to read this map":"如何阅读此图","Review notes":"审阅备注","About depth":"关于深度","Historical analysis keeps its original language; new runs use the current language.":"历史分析保留原语言；新运行按当前语言生成","历史分析保留原语言；新运行按当前语言生成":"历史分析保留原语言；新运行按当前语言生成"},
    en: {"语言":"Language","本地工作区":"Local workspace","连接 Codex":"Connect Codex","开始探索":"START AN EXPLORATION","一篇论文，一个更深的问题。":"One paper. A deeper question.","从标题、DOI 或 arXiv 链接开始。":"Start with a title, DOI, or arXiv link.","你想追踪哪篇论文？":"Which paper do you want to trace?","探索预算":"Exploration budget","轮次":"Rounds","每轮阅读":"Read / round","每轮候选":"Candidates / round","模型调用":"Model calls","时间限制（分钟）":"Time limit (min)","可选":"optional","工作硬限制，不保证研究完整性。":"Hard limits on work, not a guarantee of research completeness.","追踪这篇论文":"Trace this paper","查看示例演示":"Explore an illustrative demo","演示使用合成示例，不需要登录或模型调用。":"Demo uses synthetic examples. No login or model calls.","你的探索":"YOUR EXPLORATIONS","你的研究历史会显示在这里。":"Your research history will appear here.","回收站":"Trash","已删除的探索可在这里恢复。":"Deleted explorations can be restored here.","恢复":"Restore","删除":"Delete","研究全景":"THE RESEARCH LANDSCAPE","追踪背后的逻辑。":"Follow the underlying logic.","从一篇论文，到塑造后续工作的那些问题。":"From one paper to the problems that shaped what came next.","研究演进":"RESEARCH EVOLUTION","分支探索":"BRANCHED EXPLORATION","停止探索":"Stop exploration","前往运行中的探索":"Go to running exploration","停止运行":"Stop running","从这里创建分支 ↗":"Branch from here ↗","导出 HTML ↓":"Export HTML ↓","已保存快照":"Saved snapshot","有依据的连接":"Supported connection","假设":"Hypothesis","适配":"Fit","补充背景":"Background","种子":"SEED","年份":"YEAR","未标日期":"Undated","篇论文":"papers","个连接":"connections","深度":"depth","本轮没有纳入论文，请检查缺口和活动记录。":"This iteration has no included papers. Review its gaps and activity.","背景角色":"Context role","模型连接":"MODEL CONNECTION","连接 Codex 运行时":"Connect your Codex runtime","从好奇开始":"START WITH CURIOSITY","论文详情":"PAPER DETAIL","连接详情":"CONNECTION DETAIL","探索笔记":"EXPLORATION NOTES","解决的问题":"Problem addressed","机制变化":"Change in mechanism","结果与影响":"Results and consequences","局限":"Limitations","假设与条件":"Assumptions & conditions","不确定性":"Uncertainty","关联工作":"Connected work","证据":"Evidence","示例来源材料":"Illustrative source material","来源证据":"Source evidence","未解决的问题":"Unresolved gaps","本轮变化":"Changes in this iteration","研究范围":"Research scope","如何阅读此图":"How to read this map","审阅备注":"Review notes","关于深度":"About depth","历史分析保留原语言；新运行按当前语言生成":"Historical analysis keeps its original language; new runs use the current language."}
  };
  Object.assign(translations.zh, {
    "available": "已有候选",
    "pending_scan": "仍有邻域未扫描",
    "none_found_in_scanned_neighborhood": "已扫描邻域中未找到",
    "Synthesis did not explain every analyzed paper within the revision or model-call budget. The unfinished tree and sources are saved; no incomplete iteration was published as complete.": "在修订次数或模型调用预算内，仍未完成对全部已分析论文的解释。未完成的树和来源已保存，本轮未作为完成版本发布。",
    "Inspecting direct citations and references of the current seed mainline for unexplained work and different accounts.": "正在检查当前种子主线的双向直接引用，寻找尚未解释的工作和不同解释。",
    "A citation lookup was unavailable; no open-topic search fallback was used.": "引用查询暂不可用；未改用开放主题搜索。"
  });
  Object.assign(translations.zh, {"Running":"运行中","Queued":"排队中","Pending":"等待中","Starting":"启动中","Stopping":"停止中","Completed":"已完成","Stopped":"已停止","Failed":"失败","Budget exhausted":"达到预算上限","Preparing":"准备中","candidates":"候选","read":"阅读","included":"纳入","model calls":"模型调用","seconds":"秒","usage":"用量","reported calls":"已报告调用","unreported":"未报告","Connected":"已连接","Connect Codex":"连接 Codex","Codex runtime not found. Install the Codex CLI to enable live research.":"找不到 Codex 运行时，请安装 Codex CLI 以启用实时研究。","Saved version":"已保存版本","No saved iteration yet":"尚无已保存迭代","Supported connection":"有依据的连接","Hypothesis":"假设","Evidence first. Connections with context.":"证据优先，连接需要上下文。","Snapshots preserve every iteration.":"快照会保留每一轮迭代。","Time runs downward. Colored columns group discovered intent; cross-column links preserve shared mechanisms. Select a paper or connection to inspect its evidence.":"时间由上至下。彩色列按发现的意图分组；跨列连接保留共享机制。选择论文或连接查看证据。","Keep the evidence.":"保留证据。","More than a collection.\nA chain of understanding.":"不只是收藏。\n而是一条理解的链路。","Trace what each method changed, which problem it addressed, and what remained unresolved.":"追踪每种方法改变了什么、解决了什么问题，以及留下了哪些未解之处。","Depth counts supported problem transitions.":"深度统计有依据的问题转变。","Discover the connections.":"发现连接。","A workspace for research evolution":"研究演进工作区","Local workspace":"本地工作区","Running":"运行中","Prioritizing later citing papers and recent independent work; earlier context requires a specific later problem.":"优先查找较新的引用论文和独立工作；较早背景只有在后续论文提出具体问题时才纳入。","Looking up limited earlier context for an evidenced problem in a later paper.":"正在为后续论文中有证据的问题查找有限的早期背景。","A recovered publication date precedes the seed; retained as metadata without entering the analysis.":"恢复的发表日期早于种子论文；保留为元数据，不纳入分析。","Searching across the seed year through the present, including missing transitions and counterexamples.":"正在从种子论文年份检索至今，覆盖缺失的转变和反例。","Revising the explanation against uncovered papers and source evidence.":"正在根据尚未解释的论文和来源证据修订解释。","Re-reading source evidence for unresolved explanation links.":"正在重新阅读来源证据，以解决未解释的关联。","A citation lookup was unavailable; the affected years remain unscanned, not empty.":"引用查询暂不可用；受影响年份仍未扫描完，不代表为空。","Selecting citation neighbors year by year from the seed year to the present; missing years keep their own search gaps.":"正在从种子年份到现在逐年选择引用邻居；缺失年份保留各自的检索缺口。"});
  Object.assign(translations.zh, {"Unfinished working draft":"未完成工作草稿","Continue synthesis":"继续归纳现有资料","Resume synthesis with remaining budget":"按剩余预算继续归纳","candidate pool":"去重候选文献池","candidate offers":"候选供给","synthesis budget":"归纳预算","minutes remaining":"剩余分钟","Missing source connections":"缺少来源连接","Unconnected papers":"未连接论文","invalid_member_evidence":"成员证据无效","missing_member_support":"缺少成员支持","missing_spine":"缺少主线","unexplained_members":"成员尚未解释","invalid_spine_transition":"主线转变无效","invalid_member_evidence":"成员证据无效","Unfinished working draft — not a completed iteration":"未完成工作草稿——不是已完成迭代","Continue synthesis":"继续归纳现有资料","Synthesis incomplete":"归纳未完成","Completion diagnostics":"完成诊断","Unexplained members":"未解释成员","Quality notes":"质量备注","This is a working draft; it is not a completed iteration and cannot be exported or branched.":"这是工作草稿，不是已完成迭代，不能导出或创建分支。"});
  Object.assign(translations.zh, {
  "Track the problems, mechanisms, and unresolved questions that connect this work.": "追踪连接这些工作的具体问题、机制变化与未解之处。",
  "ILLUSTRATIVE DEMO": "合成演示",
  "DEMO": "演示",
  "LIVE": "研究",
  "Round": "轮次",
  "rounds": "轮",
  "Branch round": "分支轮次",
  "saved": "已保存",
  "saved iteration": "保存的迭代",
  "Activity": "活动",
  "VERSION": "版本",
  "Iteration": "迭代",
  "iteration": "迭代",
  "latest": "最新",
  "Immutable export": "不可变导出",
  "Viewing saved iteration": "正在查看迭代",
  "following latest": "跟随最新",
  "pinned version": "固定版本",
  "in": "输入",
  "out": "输出",
  "cached": "缓存输入",
  "unknown": "未知",
  "The shape of the question": "问题的演进结构",
  "SUPPORTED DEPTH": "有依据的深度",
  "INCLUDED PAPERS": "纳入论文",
  "SUPPORTED LINKS": "有依据的连接",
  "OPEN QUESTIONS": "未解问题",
  "Illustrative demonstration. This tree uses synthetic examples to show the workflow; it is not a verified literature review.": "此树使用虚构示例演示工作流程，不是经核实的文献综述。",
  "Depth counts supported, chronological problem transitions. Additional papers, layout rows, and hypotheses do not by themselves make an explanation deeper.": "深度统计按时间递进且有依据的问题转变。论文数量、排版行数和假设本身不会增加解释深度。",
  "OR USE AN API KEY": "或使用 API 密钥",
  "Sign in with ChatGPT ↗": "通过 ChatGPT 登录 ↗",
  "Connect with API key": "使用 API 密钥连接",
  "Check connection": "检查连接",
  "Sign out": "退出登录",
  "OpenAI API key": "OpenAI API 密钥",
  "Use an existing local Codex session, sign in with ChatGPT, or provide an API key. Credentials are excluded from research snapshots and exports.": "使用现有本地 Codex 会话、登录 ChatGPT，或提供 API 密钥。研究快照与导出不会包含凭据。",
  "API usage is billed separately. The key is passed to the local Codex runtime.": "API 使用单独计费，密钥交给本地 Codex 运行时管理。",
  "Codex remaining quota ↗": "查看 Codex 剩余额度 ↗",
  "Codex is available. Sign in to begin live research.": "Codex 已就绪，登录后可以开始研究。",
  "Connected through an API key.": "已通过 API 密钥连接。",
  "Connected through your local Codex session.": "已通过本地 Codex 会话连接。",
  "Connected. You can close this window and start an exploration.": "已连接，可以关闭此窗口并开始探索。",
  "Continue in your browser ↗": "在浏览器中继续 ↗",
  "Enter this code if requested:": "如有提示，请输入此代码：",
  "After signing in, select “Check connection” below.": "登录后，请点击下方“检查连接”。",
  "Login started. Follow the local Codex sign-in instructions, then check the connection.": "登录已启动，请按照本地 Codex 的提示操作，然后检查连接。",
  "Enter an API key first.": "请先输入 API 密钥。",
  "Enter a paper title, DOI, or arXiv link to begin.": "请输入论文标题、DOI 或 arXiv 链接。",
  "Read the original paper ↗": "阅读论文原文 ↗",
  "Open source ↗": "打开来源 ↗",
  "Date unknown": "日期未知",
  "Source status unknown": "来源状态未知",
  "Fulltext": "全文",
  "Abstract only": "仅摘要",
  "Metadata only": "仅元数据",
  "Synthetic demo": "合成演示",
  "Discovered intent": "发现的共同意图",
  "Compare underlying problems": "比较底层问题",
  "Compare with": "对比",
  "CROSS-PAPER COMPARISON": "跨论文比较",
  "Shared problem": "共同问题",
  "Earlier limitation": "前序局限",
  "What the later work changes": "后续工作改变了什么",
  "Remaining gap": "仍存缺口",
  "Grouping rationale": "分组理由",
  "Evidence boundary": "证据边界",
  "Earlier problem": "前序问题",
  "How the later work responds": "后续工作如何回应",
  "Consequence": "结果",
  "Reason for this connection": "连接依据",
  "Conditions": "适用条件",
  "Papers": "论文",
  "Revision history": "修改历史",
  "First included": "首次纳入",
  "Common problem": "共同问题",
  "Progression": "递进",
  "Open problem": "未解问题",
  "Intent group": "意图分组",
  "Alternative": "替代方案",
  "Complementary": "互补",
  "Unrelated": "无关联",
  "Insufficient evidence": "证据不足",
  "Merge": "合并",
  "Keep separate": "保留分组",
  "Uncertain": "不确定",
  "Supported": "有依据",
  "Rejected": "已否定",
  "Addresses": "回应问题",
  "Builds on": "建立于",
  "Challenges": "提出挑战",
  "Related": "相关",
  "Added": "新增",
  "Updated": "更新",
  "Removed": "移除",
  "No source excerpts are attached to this item.": "此项尚未附有来源摘录。",
  "Synthetic example excerpt · not research evidence": "虚构示例摘录，不是研究证据",
  "Excerpt verified against retrieved source": "已核对摘录与获取的原文一致",
  "Excerpt not independently verified": "摘录尚未独立核验",
  "No quoted passage attached.": "未附引文。",
  "Location unspecified": "位置未注明",
  "These excerpts are invented demonstration material, not retrieved publications or scientific evidence.": "这些摘录是虚构的演示材料，不是获取的出版物或科学证据。",
  "A verified excerpt establishes attribution, not the truth of a scientific claim.": "摘录核验仅确认出处，不能证明科学主张为真。",
  "Both papers have matching source excerpts. This is a proposed technical comparison; quotation matching does not prove the interpretation or historical influence.": "两篇论文都有可核对的原文摘录。此技术比较仍是待审阅的解释；引文匹配不能证明解释或历史影响。",
  "Evidence from both papers has not been established. This comparison remains uncertain.": "尚未建立来自两篇论文的证据，这项比较仍不确定。",
  "Following the first connections.": "正在追踪最初的连接。",
  "No saved research tree yet.": "尚无已保存的研究树。",
  "A version appears after a complete iteration. Follow the activity above while sources are being examined.": "完成一轮后会出现新版本，阅读材料期间可查看上方活动。",
  "Check the activity and stop reason. You can begin another exploration from the same seed.": "请查看活动和停止原因，可以从同一种子开始新的探索。",
  "No completed iteration yet - analysis in progress": "尚无完成的迭代，分析正在进行",
  "No saved iteration for this exploration": "此次探索尚无已保存迭代",
  "More than a collection. A chain of understanding.": "不只是收藏，而是一条理解的链路。",
  "An open problem": "一个未解问题",
  "Where the question begins": "问题的起点",
  "A change in mechanism": "机制的变化",
  "How a later idea responds": "后续想法如何回应",
  "The next limitation": "下一个局限",
  "What opens a new direction": "什么开启了新方向",
  "↓ Time moves down": "↓ 时间从上向下",
  "↔ Shared intent groups ideas": "↔ 共同意图形成分组",
  "Saved research snapshot": "已保存的研究快照",
  "Emerging connections": "待形成的连接",
  "Work awaiting a supported intent grouping.": "等待有依据的共同意图分组。",
  "Starting": "启动中",
  "Resolving": "确认论文身份",
  "Reading seed": "阅读种子论文",
  "Discovery": "检索后续工作",
  "Background": "补充背景",
  "Exploration": "探索",
  "Reading": "阅读",
  "Synthesis": "归纳",
  "Paper assessment": "核对论文证据",
  "The search results did not unambiguously identify the seed. Use a DOI, arXiv link, or a more specific title.": "检索结果未能唯一确认种子论文。请使用 DOI、arXiv 链接或更准确的标题。",
  "The seed was not found in supported scholarly sources. Check the identifier or title.": "未在支持的论文来源中找到种子论文，请核对标识符或标题。",
  "Retrieving or parsing the scholarly source could not complete. Try again later.": "论文来源获取或解析失败，请稍后重试。",
  "The model operation could not complete. Check the local Codex runtime configuration and try again.": "模型调用未能完成，请检查本地 Codex 运行时配置后重试。",
  "The run encountered an internal error before completing this step.": "程序在完成当前步骤前发生内部错误。",

  "Reanalyzing the same cached sources with a fresh explanation; no new literature search is performed.": "正在使用同一批已读材料重新归纳，不增加新论文。",
  "Building one fresh structure from the completed source assessments.": "已完成分批证据核对，正在重建主线。",
  "Consolidation": "合并审查",
  "Evidence reading": "补读证据",
  "Continuing the saved synthesis from cached sources; missing evidence may trigger targeted rereading.": "正在从缓存材料继续归纳；证据缺口可能触发定向回读。",
  "Local synthesis": "局部归纳",
  "Relation review": "关系证据审查",
  "Regrouping": "主线归并",
  "Evidence feedback": "缺口交回探索",
  "Reading targeted passages for a specific explanation gap.": "正在针对具体解释缺口补读相关段落。",
  "Returning evidence gaps to discovery before the next refinement.": "正在把证据缺口交回检索，以便下一轮修订。",
  "Comparing the revised explanation with the best saved candidate.": "正在将修订后的解释与已保存的最佳候选比较。",
  "Reviewing proposed technical relations against their source evidence.": "正在根据来源证据审查拟议的技术关系。",
  "Consolidating shared problems to reduce branches and deepen the mainline.": "正在归并共同问题，减少分支并深化主线。",
  "Snapshot": "保存快照",
  "Demo exploration": "演示探索",
  "Demo synthesis": "演示归纳",
  "Needs source": "需要原文",
  "Interrupted": "已中断",
  "Active explorations cannot be moved to Trash.": "运行中的探索不能移入回收站。",
  "Active explorations cannot be deleted": "运行中的探索不能删除",
  "Move this exploration to Trash": "将此探索移至回收站",
  "Restore this exploration to history": "将此探索恢复到历史记录",
  "Moved to Trash. You can restore it from the sidebar.": "已移入回收站，可从侧边栏恢复。",
  "Another exploration is already running. Go to it or stop it before starting a new one.": "已有探索正在运行，请前往查看或停止后再开始。",
  "Another exploration is running. Finish or stop it before starting or branching.": "已有探索正在运行，完成或停止后才能开始新探索或创建分支。",
  "Show exploration overview": "查看探索概览",
  "Zoom out": "缩小",
  "Zoom in": "放大",
  "Reported token usage from completed model calls; totals can be incomplete while calls remain unreported.": "已报告的模型调用 token 用量；未报告的调用可能使总数不完整。",
  "Resolving the seed paper's identity. No latest endpoint or mechanism is preselected.": "正在确认种子论文身份，未预设最新终点或技术机制。",
  "Recovering seed-paper content across supported sources before defining the research question.": "正在从可用来源获取种子论文内容，然后定义研究问题。",
  "Reading selected source passages; previously cached extractions are reused.": "正在阅读选定的原文段落，复用之前缓存的提取结果。",
  "One literature lookup was unavailable; continuing with the available candidates.": "一个文献查询暂不可用，继续处理可用候选。",
  "Checking fragmented groups against shared problems and explicit merge decisions.": "正在根据共同问题和合并判断检查分组是否过于碎片化。",
  "The model-call budget was reached. Completed snapshots are preserved.": "已达到模型调用上限，完成的快照已保留。",
  "The elapsed-time budget was reached. Completed snapshots are preserved.": "已达到时间上限，完成的快照已保留。",
  "Stopped at the user's request. Completed snapshots are preserved.": "已按用户要求停止，完成的快照已保留。",
  "The iteration budget was reached. The tree remains a reviewable hypothesis, not an exhaustive research history.": "已达到迭代上限。此树仍是可审阅的解释，并非完整研究史。",
  "Two rounds selected no new sources. This is a bounded search outcome, not evidence of exhaustive coverage.": "连续两轮未选出新材料。这是有限检索的结果，不代表文献已穷尽。",
  "Synthetic preview finished. It demonstrates the interface, not research quality.": "合成演示已完成，用于展示界面，不代表研究质量。"
});
  Object.assign(translations.zh, {
    "The seed has only bibliographic metadata after source recovery. No model analysis was started; a readable abstract or full text is required.": "未能获取种子论文的摘要或正文，只有书目信息。尚未调用模型；请稍后重试，或使用准确的 DOI / arXiv 链接。",
    "Reason": "原因"
  });
  Object.assign(translations.zh,{"Sidebar":"侧边栏","Open sidebar":"打开侧边栏","Empty trash":"清空回收站","Dismiss notice":"关闭通知","TRASH":"回收站","Empty Trash?":"清空回收站？","This permanently deletes the deleted explorations currently shown in Trash.":"这将永久删除回收站中当前显示的探索。","Cancel":"取消","Permanently delete":"永久删除","Trash emptied permanently.":"已永久清空回收站。","Affiliation not established":"机构信息未获取","included_saved":"已入图（已保存）","pending synthesis":"待综合","Citation boundary":"引用边界","Connected":"已连接","Close confirmation":"关闭确认"});
  Object.assign(translations.zh,{"Source dispositions":"来源处置","deferred":"暂缓纳入","out_of_scope":"超出范围","pending":"待处理","included":"已纳入","pending synthesis":"待综合"});
  Object.assign(translations.zh,{"Citation boundary":"引用边界","Candidate boundary: papers that directly cite, or are cited by, the seed or papers integrated into the evolving mainline. Different explanations are valuable; a candidate becomes an anchor only after grounded integration.":"候选边界：直接引用种子论文或已纳入演进主线的论文，或被它们直接引用的论文。不同解释同样有价值；候选只有在有依据地纳入后才会成为主线锚点。","Citation provenance":"引用溯源","Cites mainline paper":"引用主线论文","Cited by mainline paper":"被主线论文引用","Candidate rationale":"候选理由","Current claim":"当前主张","Different story":"不同解释","Selection reason":"纳入理由","Anchor":"锚点","Problem relation":"问题关系","Same problem":"同一问题","Mechanism consequence":"机制影响","Necessary background":"必要背景","Shared domain only":"仅共享领域","Uncertain":"不确定","Open citation source ↗":"打开引用来源 ↗"});
  Object.assign(translations.en,Object.fromEntries(Object.entries(translations.zh).map(([en,zh])=>[zh,en])));
  Object.assign(translations.en,Object.fromEntries(Object.entries(translations.zh).map(([en,zh])=>[zh,en]))); Object.assign(translations.en,Object.fromEntries(Object.entries(translations.zh).map(([en,zh])=>[zh,en])));
  Object.assign(translations.zh,{"Research observations":"研究观察","claimed_problem":"作者要解决的问题","demonstrated_gain":"实际报告的收益","evaluation_protocol":"评测与比较条件","limitation":"缺陷与代价","positioning":"与前序工作的定位","author_claim":"作者自述","reported_experiment":"论文实验","model_inference":"模型推断","unknown":"未知"});
  Object.assign(translations.zh,{"Knowledge depth":"主干转折深度","Stated outcome":"作者提出的问题","Demonstrated outcome":"实际展示的结果","Conditions":"条件","Unresolved":"未解决","Role":"角色","Stage anchor":"阶段锚点","Knowledge change":"知识变化","Removal effect":"移除影响","Mainline progression":"主线推进","Unreviewed transition":"尚未审阅的转变","Supported transition":"已有依据的转变","advance":"推进","revision":"修正认识","reframing":"重新定义问题","proposal":"新方案／问题","incremental":"局部改进","replication":"复现","tooling":"工具","outcome demonstrated":"已展示","outcome partial":"部分展示","outcome not_tested":"未测试","outcome contradicted":"被反驳","outcome unknown":"未知","Semantic review":"语义审阅","Explanation quality":"解释质量"});
  Object.assign(translations.en,{"主干转折深度":"Knowledge depth","作者声称的结果":"Stated outcome","实际展示的结果":"Demonstrated outcome","条件":"Conditions","未解决":"Unresolved","角色":"Role","阶段锚点":"Stage anchor","知识变化":"Knowledge change","移除影响":"Removal effect","主线推进":"Mainline progression","尚未审阅的转变":"Unreviewed transition","已有依据的转变":"Supported transition","推进":"advance","修订":"revision","重新定义问题":"reframing","提案":"proposal","渐进":"incremental","复现":"replication","工具":"tooling","已展示":"demonstrated","部分展示":"partial","未测试":"not tested","被反驳":"contradicted","语义审阅":"Semantic review","解释质量":"Explanation quality"});
  Object.assign(translations.zh,{"Synthesis incomplete":"归纳未完成","Incomplete synthesis":"归纳未完成","Pending synthesis":"归纳未完成","Core concept":"核心目标","Explanatory claim":"关系命题","Constraint":"约束","Mechanism":"机制","Consequence":"结果","Unexplained members":"待解释成员","Annual coverage":"年度覆盖","Not all papers in a year were scanned; this does not mean no other papers exist.":"该年份尚未扫描完；这不代表不存在其他论文。","Quality notes":"质量说明"});
  Object.assign(translations.en,Object.fromEntries(Object.entries(translations.zh).map(([en,zh])=>[zh,en])));
  let preferredLanguage = "zh"; try { preferredLanguage = localStorage.getItem("deepanalyze-language") === "en" ? "en" : "zh"; } catch {}
  const ui = (value) => {
    if (preferredLanguage !== "zh") return value;
    if (translations.zh[value]) return translations.zh[value];
    for (const [suffix, translated] of [[" A saved draft is available to resume.", " 已保留草稿，可继续归纳。"], [" No completed snapshot was published.", " 本次未发布完成的快照。"]]) {
      if (typeof value === "string" && value.endsWith(suffix)) {
        const base=value.slice(0,-suffix.length);
        if (translations.zh[base]) return translations.zh[base]+translated;
      }
    }
    let match = /^Running the (exploration|paper_assessment|synthesis|consolidation|evidence_reading|local_synthesis|relation_review|regrouping|evidence_feedback) role within the configured model-call budget\.$/.exec(value);
    if (match) return `正在执行${({exploration:"探索",paper_assessment:"论文证据核对",synthesis:"归纳",consolidation:"合并审查",evidence_reading:"补读证据",local_synthesis:"局部归纳",relation_review:"关系证据审查",regrouping:"主线归并",evidence_feedback:"缺口交回探索"})[match[1]]}，受配置的调用预算限制。`;
    match = /^Assessing source batch (\d+)\.$/.exec(value);
    if (match) return `正在核对第 ${match[1]} 批论文的主张与证据，每批最多 7 篇。`;
    match = /^Saved immutable (?:synthetic snapshot|iteration) (\d+)[.;](.*)$/.exec(value);
    if (match) return `已保存不可变的第 ${match[1]} 轮快照。`;
    return value;
  };
  const activeStatuses = new Set(["queued", "pending", "running", "starting", "stopping"]);
  const palette = ["#8ecb78", "#70c9c8", "#b99be2", "#d4ae72", "#83b7e7", "#df9198"];
  const state = {token: "", runs: [], trash: [], trashPurgeIds: [], sidebarCollapsed: false, noticeDismissed: false, lastInspectorKey: "", run: null, snapshot: null, snapshotId: null, snapshotDraft: false, followLatest: true, selected: null, focus: null, activeRunId: null, zoom: 1, overviewFit: true, fitFrame: null, timer: null, polling: false, auth: null, busy: false, groups: [], requestEpoch: 0};
  const text = (value) => value == null ? "" : typeof value === "string" ? value : typeof value === "number" ? String(value) : value.name || value.label || value.description || value.text || JSON.stringify(value);
  const list = (value) => value == null ? [] : Array.isArray(value) ? value : [value];
  const nice = (value) => ui(text(value).replace(/[_-]/g, " ").replace(/^\w/, (letter) => letter.toUpperCase()));
  const el = (tag, className, content) => { const item = document.createElement(tag); if (className) item.className = className; if (content != null) item.textContent = text(content); return item; };
  const safeURL = (value) => { try { const parsed = new URL(value); return ["https:", "http:"].includes(parsed.protocol) ? parsed.href : null; } catch { return null; } };
  const shortDate = (value) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? "Saved version" : date.toLocaleDateString(preferredLanguage === "zh" ? "zh-CN" : "en", {month:"short", day:"numeric"}); };
  const timeOf = (value) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString(preferredLanguage === "zh" ? "zh-CN" : "en", {hour:"2-digit", minute:"2-digit"}); };
  const active = (run) => !!run && activeStatuses.has(run.status);
  const elapsedSeconds = (run) => {
    const recorded = Number(run?.progress?.elapsed_seconds) || 0;
    const started = Date.parse(run?.created_at || "");
    return Math.round(active(run) && Number.isFinite(started) ? Math.max(recorded, (Date.now() - started) / 1000) : recorded);
  };
  const nodeName = (node) => node?.short_name || node?.title || node?.id || "Untitled paper";
  const seedText = (run) => typeof run?.seed === "string" ? run.seed : run?.seed?.title || run?.seed?.query || "Research exploration";

  async function api(path, options = {}) {
    const response = await fetch(path, {credentials:"same-origin", ...options, headers:{"Accept":"application/json", ...(options.body ? {"Content-Type":"application/json", "X-DeepAnalyze-Token":state.token} : {}), ...options.headers}});
    const result = await response.json().catch(() => ({}));
    if (!response.ok) { const error = new Error(text(result.error?.message || result.error || result.detail || result.message || `Request failed (${response.status})`)); error.code = result.code || result.error?.code; error.active_run_id = result.active_run_id || result.error?.active_run_id; throw error; }
    return result;
  }
  function notice(message = "", error = false) { const box=$("notice"), label=$("notice-text"); if (!message) { box.hidden=true; label.textContent=""; return; } state.noticeDismissed=false; label.textContent=ui(message); box.hidden=false; box.classList.toggle("error", error); }
  function dismissNotice() { state.noticeDismissed=true; $("notice").hidden=true; }
  function setSidebarCollapsed(collapsed) { state.sidebarCollapsed=!!collapsed; document.body.classList.toggle("sidebar-collapsed", state.sidebarCollapsed); const button=$("sidebar-toggle"); button.setAttribute("aria-expanded",String(!state.sidebarCollapsed)); button.querySelector("span").textContent=ui(state.sidebarCollapsed?"Open sidebar":"Sidebar"); try{localStorage.setItem("deepanalyze-sidebar-collapsed",state.sidebarCollapsed?"1":"0");}catch{} }
  function setBusy(value) { state.busy = value; renderRunActions(); renderRuns(); renderTrash(); }
  async function withAction(action) { if (state.busy) return; setBusy(true); notice(); try { await action(); } catch (error) { if (error.code === "exploration_active" || error.active_run_id) { await refreshState().catch(() => {}); renderActiveRunBanner(); notice("Another exploration is already running. Go to it or stop it before starting a new one.", true); } else notice(error.message, true); } finally { setBusy(false); renderRunActions(); } }
  function numeric(id, fallback, min, max) { const value = Number($(id).value); return Number.isFinite(value) ? Math.max(min, Math.min(max, Math.round(value))) : fallback; }
  function config() { return {max_iterations:numeric("budget-rounds",10,1,20), read_per_round:numeric("budget-read",10,1,30), candidates_per_round:numeric("budget-candidates",30,1,60), max_model_calls:numeric("budget-calls",100,1,100), max_seconds:numeric("budget-time",300,1,300)*60, model:$("model-input").value.trim(), language:preferredLanguage}; }

  function renderRuns() {
    $("runs-count").textContent = state.runs.length;
    const container = $("run-list"); container.replaceChildren();
    if (!state.runs.length) { container.append(el("p", "quiet-empty", ui("Your research history will appear here."))); return; }
    for (const run of state.runs) {
      const row = el("div", `run-row${state.run?.id === run.id ? " active" : ""}`);
      const button = el("button", "run-item"); button.type = "button"; button.title = seedText(run); button.setAttribute("aria-current", state.run?.id === run.id ? "true" : "false");
      button.append(el("strong", "", seedText(run)));
      const meta = el("small"); meta.append(el("span", "", `${shortDate(run.created_at)} · ${nice(run.status)}`), el("span", "run-mode", ui(run.mode === "demo" ? "DEMO" : "LIVE"))); button.append(meta);
      button.addEventListener("click", () => { if (run.id !== state.run?.id) selectRun(run.id).catch((error) => notice(error.message,true)); });
      const trash = el("button", "run-trash", ui("Delete")); trash.type = "button"; trash.title = ui(active(run) ? "Active explorations cannot be deleted" : "Move this exploration to Trash"); trash.disabled = active(run) || state.busy; trash.setAttribute("aria-label", `Move ${seedText(run)} to Trash`); trash.addEventListener("click", (event) => { event.stopPropagation(); withAction(() => trashRun(run.id)); });
      row.append(button, trash); container.append(row);
    }
  }
  function renderTrash() {
    const container = $("trash-list"); if (!container) return; $("trash-count").textContent = state.trash.length; $("trash-empty").hidden = !state.trash.length || state.busy; container.replaceChildren();
    if (!state.trash.length) { container.append(el("p", "quiet-empty", ui("Deleted explorations can be restored here."))); return; }
    for (const item of state.trash) { const row = el("div", "trash-row"); row.append(el("span", "trash-name", seedText(item))); const restore = el("button", "button button-small button-quiet", ui("Restore")); restore.type = "button"; restore.disabled = state.busy; restore.title = ui("Restore this exploration to history"); restore.addEventListener("click", () => withAction(() => restoreRun(item.id))); row.append(restore); container.append(row); }
  }
  async function refreshState() {
    const result = await api("/api/state"); state.token = result.csrf_token || state.token; state.runs = result.runs || []; state.activeRunId = result.active_run_id || state.runs.find(active)?.id || null; renderRuns(); renderActiveRunBanner(); await refreshTrash(); return result;
  }
  async function refreshTrash() { try { const result = await api("/api/trash"); state.trash = result.trash || result.runs || (Array.isArray(result) ? result : []); renderTrash(); } catch (error) { state.trash = []; renderTrash(); } }
  async function trashRun(id) {
    const run = state.runs.find((item) => item.id === id);
    if (!run || active(run)) throw new Error("Active explorations cannot be moved to Trash.");
    await api(`/api/runs/${encodeURIComponent(id)}/trash`, {method:"POST", body:"{}"});
    const wasSelected = state.run?.id === id;
    if (wasSelected) { ++state.requestEpoch; state.run = null; state.selected = null; state.snapshot = null; state.snapshotId = null; }
    await refreshState();
    if (wasSelected) {
      const next = state.runs.find((item) => item.id === state.activeRunId) || state.runs[0];
      if (next) await selectRun(next.id);
      else {
        $("workspace-title").textContent = "Follow the underlying logic.";
        $("workspace-eyebrow").textContent = "THE RESEARCH LANDSCAPE";
        $("workspace-subtitle").textContent = "From one paper to the problems that shaped what came next.";
        $("mode-badge").hidden = true;
        $("empty-state").hidden = false;
        $("empty-state").querySelector("h2").textContent = "More than a collection. A chain of understanding.";
        $("empty-state").querySelector(":scope > p").textContent = "Trace what each method changed, which problem it addressed, and what remained unresolved.";
        for (const id of ["map-pane", "inspector", "map-toolbar", "run-progress"]) $(id).hidden = true;
        $("save-status").textContent = "Snapshots preserve every iteration.";
      }
    }
    notice("Moved to Trash. You can restore it from the sidebar.");
  }
  async function restoreRun(id) { await api(`/api/runs/${encodeURIComponent(id)}/restore`, {method:"POST", body:"{}"}); await refreshState(); }  async function purgeTrash() { const ids=state.trashPurgeIds.slice(); if(!ids.length) return; const dialog=$("trash-purge-dialog"); if(dialog.open) dialog.close(); await api("/api/trash/purge",{method:"POST",body:JSON.stringify({run_ids:ids,confirm:true})}); state.trashPurgeIds=[]; await refreshTrash(); notice("Trash emptied permanently."); }
  function openTrashPurge() { state.trashPurgeIds=state.trash.map((item)=>item.id).filter(Boolean); if(!state.trashPurgeIds.length) return; const copy=$("trash-purge-copy"); copy.textContent=`${ui("This permanently deletes the deleted explorations currently shown in Trash.")} (${state.trashPurgeIds.length})`; $("trash-purge-dialog").showModal(); }

  function applyLanguage() {
    document.documentElement.lang = preferredLanguage === "zh" ? "zh-CN" : "en"; const select = $("language-select"); if (select) select.value = preferredLanguage;
    const labels = {"environment-label":"Local workspace","auth-label":"Connect Codex","workspace-eyebrow":"THE RESEARCH LANDSCAPE","workspace-title":"Follow the underlying logic.","workspace-subtitle":"From one paper to the problems that shaped what came next.","language-boundary":"Historical analysis keeps its original language; new runs use the current language."};
    for (const [id,value] of Object.entries(labels)) if ($(id)) $(id).textContent = ui(value);
    const mapping = [[".composer .section-eyebrow","START AN EXPLORATION"],[".composer .input-label","One paper. A deeper question."],[".composer .field-hint","Start with a title, DOI, or arXiv link."],[".budget-details summary","Exploration budget"],[".budget-grid label:nth-child(1)","Rounds"],[".budget-grid label:nth-child(2)","Read / round"],[".budget-grid label:nth-child(3)","Candidates / round"],[".budget-grid label:nth-child(4)","Model calls"],[".budget-grid label:nth-child(5)","Time limit (min)"],["#start-button","Trace this paper"],["#demo-button","Explore an illustrative demo"],[".demo-hint","Demo uses synthetic examples. No login or model calls."],[".runs-section .section-eyebrow","YOUR EXPLORATIONS"],["#trash-details summary","Trash"],["#stop-button","Stop exploration"],["#resume-button","Branch from here ↗"],["#export-button","Export HTML ↓"],["#mode-badge","ILLUSTRATIVE DEMO"],[".language-picker span","Language"],["#sidebar-toggle span","Sidebar"],["#trash-empty","Empty trash"],["#notice-dismiss","Dismiss notice"],["#trash-purge-dialog .section-eyebrow","TRASH"],["#trash-purge-title","Empty Trash?"],["#trash-purge-copy","This permanently deletes the deleted explorations currently shown in Trash."],["#trash-purge-confirm","Permanently delete"],["#trash-purge-dialog .button[value=cancel]","Cancel"],[".brand-caption","A workspace for research evolution"],[".activity-details summary","Activity"],[".version-control label","VERSION"],[".map-legend span:nth-child(1)","Supported connection"],[".map-legend span:nth-child(2)","Hypothesis"],["#zoom-fit","Fit"],[".map-footer span:last-child","Depth counts supported problem transitions."],[".workspace-bottom span:first-child","Evidence first. Connections with context."],[".auth-divider span","OR USE AN API KEY"],["#chatgpt-login","Sign in with ChatGPT ↗"],["#api-login","Connect with API key"],["#auth-refresh","Check connection"],["#auth-logout","Sign out"],["#auth-dialog .input-label","OpenAI API key"],["#save-status","Snapshots preserve every iteration."],[".empty-eyebrow","START WITH CURIOSITY"],[".empty-state h2","More than a collection.\nA chain of understanding."],[".empty-state > p","Trace what each method changed, which problem it addressed, and what remained unresolved."],["#auth-dialog .section-eyebrow","MODEL CONNECTION"],["#auth-title","Connect your Codex runtime"],[".dialog-description","Use an existing local Codex session, sign in with ChatGPT, or provide an API key. Credentials are excluded from research snapshots and exports."]];
    for (const [selector,value] of mapping) { const node=document.querySelector(selector); if (node) { if (node.matches("label") && node.firstChild) node.firstChild.textContent=ui(value); else if (node.matches("span") && node.querySelector("i")) { const textNode=[...node.childNodes].find((child)=>child.nodeType===Node.TEXT_NODE); if(textNode) textNode.textContent=ui(value); } else if ((selector.includes("summary") || node.matches("span")) && node.firstChild && node.firstChild.nodeType === Node.TEXT_NODE) node.firstChild.textContent=ui(value)+" "; else if (node.matches("button") && node.querySelector("span")) node.firstChild.textContent=ui(value)+" "; else node.textContent=ui(value); } }
    const footer = document.querySelector(".sidebar-footer p"); if (footer) { const first = [...footer.childNodes].find((child) => child.nodeType === Node.TEXT_NODE); if (first) first.textContent = ui("Keep the evidence.")+"\n"; const strong = footer.querySelector("strong"); if (strong) strong.textContent = ui("Discover the connections."); }
    const apiKey=$("api-key"); if(apiKey) apiKey.placeholder=preferredLanguage === "zh" ? "粘贴 API 密钥" : "Paste your API key";
    const seed=$("seed-input"); if(seed) seed.placeholder=ui("Which paper do you want to trace?");
    const read=$("budget-read"); if(read) read.parentElement.firstChild.textContent=ui("Read / round");
    const candidates=$("budget-candidates"); if(candidates) candidates.parentElement.firstChild.textContent=ui("Candidates / round");
    $("budget-summary").textContent = `${numeric("budget-rounds",10,1,20)} ${ui("rounds")}`;
    $("environment-label").textContent = ui(exported ? "Saved research snapshot" : "Local workspace");
    if (state.auth) renderAuth();
    for (const [selector, value] of [[".budget-note","Hard limits on work, not a guarantee of research completeness."],[".quota-link","Codex remaining quota ↗"],["#auth-dialog .field-hint","API usage is billed separately. The key is passed to the local Codex runtime."],[".sample-one strong","An open problem"],[".sample-one div span","Where the question begins"],[".sample-two strong","A change in mechanism"],[".sample-two div span","How a later idea responds"],[".sample-three strong","The next limitation"],[".sample-three div span","What opens a new direction"],[".empty-footer span:first-child","↓ Time moves down"],[".empty-footer span:last-child","↔ Shared intent groups ideas"]]) {
      const node = document.querySelector(selector); if (node) node.textContent = ui(value);
    }
    for (const [id, title] of [["zoom-out","Zoom out"],["zoom-in","Zoom in"],["close-inspector","Show exploration overview"]]) $(id).title = ui(title);
    const purgeClose=$("trash-purge-dialog")?.querySelector(".dialog-close"); if(purgeClose) purgeClose.setAttribute("aria-label",ui("Close confirmation")); const noticeClose=$("notice-dismiss"); if(noticeClose) noticeClose.setAttribute("aria-label",ui("Dismiss notice"));
    setSidebarCollapsed(state.sidebarCollapsed); renderRuns(); renderActiveRunBanner(); renderTrash(); if (state.run) { renderRun(); if (state.snapshot) renderSnapshot(state.snapshot); } else renderTrash();
  }
  function activeRun() { return state.runs.find((run) => run.id === state.activeRunId) || (active(state.run) ? state.run : null); }
  async function stopRunById(id) { if (!id) return; const run = await api(`/api/runs/${encodeURIComponent(id)}/stop`, {method:"POST", body:"{}"}); if (state.run?.id === id) { state.run = run.id ? run : await api(`/api/runs/${encodeURIComponent(id)}`); renderRun(); } await refreshState(); schedulePoll(); }
  function renderActiveRunBanner() {
    const banner = $("active-run-banner"); const run = activeRun();
    if (!run || exported || run.id === state.run?.id) { banner.hidden = true; banner.replaceChildren(); return; }
    banner.hidden = false; banner.replaceChildren();
    const copy = el("span", "active-run-copy", preferredLanguage === "zh" ? `已有探索正在运行：${seedText(run)}。完成或停止它后才能开始新的探索。` : `An exploration is already running: ${seedText(run)}. Start, demo, and branch actions stay disabled until it finishes.`);
    const go = el("button", "button button-small button-quiet", ui("Go to running exploration")); go.type = "button"; go.addEventListener("click", () => selectRun(run.id).catch((error) => notice(error.message, true)));
    const stop = el("button", "button button-small button-danger-quiet", ui("Stop running")); stop.type = "button"; stop.disabled = state.busy || run.status === "stopping"; stop.addEventListener("click", () => withAction(() => stopRunById(run.id)));
    banner.append(copy, go, stop);
  }
  async function selectRun(id) {
    const epoch = ++state.requestEpoch;
    const run = await api(`/api/runs/${encodeURIComponent(id)}`); if (epoch !== state.requestEpoch) return;
    state.run = run; state.followLatest = true; state.snapshotId = null; state.snapshotDraft = false; state.selected = null; state.focus = null; state.snapshot = null;
    renderRun(); renderRuns(); await showLatest(); schedulePoll();
  }
  async function showLatest() {
    const run = state.run; if (!run) return;
    const latest = run.latest_snapshot;
    if (latest && typeof latest === "object" && Array.isArray(latest.nodes)) { state.snapshotDraft = false; renderSnapshot(latest); }
    else {
      const summaries = run.snapshots || []; const id = typeof latest === "string" ? latest : summaries.at(-1)?.id;
      if (id) await loadSnapshot(id, true); else if (run.working_snapshot && Array.isArray(run.working_snapshot.nodes)) { state.snapshotDraft = true; state.snapshotId = "__working__"; renderSnapshot(run.working_snapshot); } else renderWaiting();
    }
  }
  async function loadSnapshot(id, followLatest = false) {
    if (!state.run || !id) return;
    state.followLatest = followLatest;
    const runId = state.run.id; const epoch = ++state.requestEpoch;
    if (id === "__working__") { state.snapshotDraft = true; state.snapshotId = id; state.selected = null; state.focus = null; renderSnapshot(state.run.working_snapshot); renderVersionControl(); return; }
    const snapshot = await api(`/api/runs/${encodeURIComponent(runId)}/snapshots/${encodeURIComponent(id)}`);
    if (epoch !== state.requestEpoch || runId !== state.run?.id) return;
    state.followLatest = followLatest; state.snapshotDraft = false; state.snapshotId = id; state.selected = null; state.focus = null; renderSnapshot(snapshot); renderVersionControl();
  }
  function renderWaiting() {
    $("empty-state").hidden = false; $("map-pane").hidden = true; $("inspector").hidden = true;
    $("map-toolbar").hidden = true;
    $("save-status").textContent = active(state.run) ? ui("No completed iteration yet - analysis in progress") : ui("No saved iteration for this exploration");
    const title = $("empty-state").querySelector("h2"); const copy = $("empty-state").querySelector(":scope > p");
    if (state.run) { title.replaceChildren(document.createTextNode(ui(active(state.run) ? "Following the first connections." : "No saved research tree yet."))); copy.textContent = ui(active(state.run) ? "A version appears after a complete iteration. Follow the activity above while sources are being examined." : "Check the activity and stop reason. You can begin another exploration from the same seed."); }
  }
  function renderRun() {
    const run = state.run; if (!run) return; document.body.classList.toggle("compact-running", active(run));
    $("workspace-eyebrow").textContent = ui(run.parent ? "BRANCHED EXPLORATION" : "RESEARCH EVOLUTION");
    $("workspace-title").textContent = seedText(run);
    $("workspace-subtitle").textContent = ui("Track the problems, mechanisms, and unresolved questions that connect this work.");
    $("mode-badge").hidden = run.mode !== "demo" && !state.snapshot?.demo;
    $("run-progress").hidden = !!exported;
    $("phase-label").textContent = nice(run.phase || run.status || "Preparing");
    $("phase-dot").className = `status-dot${active(run) ? " running" : run.status === "failed" ? " failed" : ""}`;
    const branchBase = run.parent ? Number((run.snapshots || []).find((item) => item.id === run.parent.snapshot_id)?.iteration ?? Math.max(0, Number(run.snapshots?.[0]?.iteration || 1) - 1)) : 0;
    const completedRounds = Math.max(0, (Number(run.iteration) || 0) - branchBase);
    const round = active(run) && run.status !== "queued" ? Math.min(completedRounds + 1, run.config?.max_iterations || Infinity) : completedRounds;
    $("phase-detail").textContent = `${nice(run.status)} · ${ui(run.parent ? "Branch round" : "Round")} ${round}${run.config?.max_iterations ? ` / ${run.config.max_iterations}` : ""}${run.parent ? ` · ${ui("saved iteration")} ${run.iteration || branchBase}` : ` · ${completedRounds} ${ui("saved")}`}`;
    const progress = run.progress || {}; const stats = $("progress-stats"); stats.replaceChildren();
    const progressItems = [[progress.candidates||0,"candidate pool"],[progress.read||0,"read"],[progress.included||0,"included_saved"],[progress.model_calls||0,"model calls"]]; if (typeof progress.pending_synthesis === "number") progressItems.push([progress.pending_synthesis,"pending synthesis"]); progressItems.push([elapsedSeconds(run),"seconds"]); const synthesisBudget=run.synthesis_budget; if (synthesisBudget && (synthesisBudget.remaining_model_calls != null || synthesisBudget.remaining_seconds != null)) { const used=synthesisBudget.model_calls_used != null ? `${synthesisBudget.model_calls_used}/${synthesisBudget.limits?.max_model_calls ?? run.config?.max_model_calls ?? "?"} ${ui("model calls")}` : ""; const left=synthesisBudget.remaining_seconds != null ? `${Math.max(0,Math.round(synthesisBudget.remaining_seconds/60))} ${ui("minutes remaining")}` : ""; progressItems.push([`${used}${used&&left?" · ":""}${left}`,"synthesis budget"]); } for (const [value,label] of progressItems) { const item = el("span"); const number = el("strong","",value); if (label === "seconds") number.id = "elapsed-seconds"; item.append(number,document.createTextNode(ui(label))); stats.append(item); }
    const usage = run.usage; if (usage && (usage.reported_calls != null || usage.total_tokens != null || usage.input_tokens != null || usage.output_tokens != null)) { const total = usage.total_tokens == null ? "unknown" : Number(usage.total_tokens).toLocaleString(); const reported = usage.reported_calls == null ? "unknown" : usage.reported_calls; const incomplete = Number(usage.unreported_calls || 0) > 0; const breakdown = [usage.input_tokens != null ? `${ui("in")} ${Number(usage.input_tokens).toLocaleString()}` : "", usage.output_tokens != null ? `${ui("out")} ${Number(usage.output_tokens).toLocaleString()}` : "", usage.cached_input_tokens != null ? `${ui("cached")} ${Number(usage.cached_input_tokens).toLocaleString()}` : ""].filter(Boolean).join(" · "); const item = el("span", incomplete ? "usage-incomplete" : "", `${ui("usage")} ${total} tokens · ${reported} ${ui("reported calls")}${breakdown ? ` · ${breakdown}` : ""}${incomplete ? ` · ${usage.unreported_calls} ${ui("unreported")}` : ""}`); item.title = "Reported token usage from completed model calls; totals can be incomplete while calls remain unreported."; stats.append(item); }
    const events = list(run.events); const activity = $("activity-log"); activity.replaceChildren();
    for (const event of events.slice(-30)) { const item = el("li"); item.append(el("time","",timeOf(event.at)),document.createTextNode(ui(text(event.message)))); activity.append(item); }
    if (run.stop_reason && !events.some((event) => event.message === run.stop_reason)) { const item = el("li"); item.append(el("strong","",`${ui("Reason")}: `),document.createTextNode(ui(text(run.stop_reason)))); activity.append(item); }
    $("latest-event").textContent = ui(run.stop_reason || events.at(-1)?.message || "");
    renderVersionControl(); renderRunActions();
  }
  function renderRunActions() {
    const anotherActive = !!state.activeRunId;
    for (const id of ["start-button", "demo-button", "resume-button"]) { const button = $(id); button.disabled = state.busy || anotherActive; button.title = anotherActive ? ui("Another exploration is running. Finish or stop it before starting or branching.") : ""; }
    renderActiveRunBanner();
    $("stop-button").hidden = !active(state.run) || !!exported;
    $("stop-button").disabled = state.run?.status === "stopping" || state.busy;
    $("resume-button").hidden = !state.snapshot || !!exported || state.snapshotDraft || active(state.run);
    const retry = $("retry-synthesis-button"); if (retry) { const canRetry = state.run?.can_retry_synthesis === true; retry.hidden = !state.snapshotDraft || !!exported || active(state.run); retry.disabled = state.busy || anotherActive || !canRetry; retry.textContent = ui("Continue synthesis"); retry.title = canRetry ? ui("Resume synthesis with remaining budget") : ui("Synthesis retry is unavailable for this run."); }
    $("resume-button").disabled = state.busy || anotherActive;
  }
  function renderVersionControl() {
    if (!state.run || !state.snapshot) return;
    $("map-toolbar").hidden = false;
    const select = $("snapshot-select"); const selected = state.snapshotDraft ? "__working__" : (state.snapshotId || state.snapshot.id);
    select.replaceChildren();
    const summaries = state.run.snapshots?.length ? state.run.snapshots : (state.snapshotDraft ? [] : [{id:state.snapshot.id,iteration:state.snapshot.iteration,created_at:state.snapshot.created_at}]);
    const newest = summaries.at(-1)?.id;
    for (const summary of summaries) {
      const option = el("option", "", `${ui("Iteration")} ${summary.iteration ?? "–"} · ${shortDate(summary.created_at)}${summary.id === newest ? ` · ${ui("latest")}` : ""}`); option.value = summary.id; select.append(option);
    }
    if (state.run.working_snapshot && Array.isArray(state.run.working_snapshot.nodes)) { const option = el("option", "", ui("Unfinished working draft")); option.value = "__working__"; select.append(option); }
    select.value = selected; select.disabled = !!exported;
    $("historical-label").hidden = !!exported || (!state.snapshotDraft && (state.followLatest || selected === newest));
    $("historical-label").textContent = ui(state.snapshotDraft ? "Unfinished working draft" : "Saved snapshot");
    $("export-button").hidden = !!exported || state.snapshotDraft;
    $("export-button").href = state.snapshotDraft ? "#" : `/api/runs/${encodeURIComponent(state.run.id)}/export?snapshot=${encodeURIComponent(selected)}`;
    $("save-status").textContent = state.snapshotDraft ? ui("Unfinished working draft — not a completed iteration") : (exported ? `${ui("Immutable export")} · ${ui("iteration")} ${state.snapshot.iteration ?? "–"}` : `${ui("Viewing saved iteration")} ${state.snapshot.iteration ?? "–"}${state.followLatest ? ` · ${ui("following latest")}` : ` · ${ui("pinned version")}`}`);
  }
  function color(group, index) {
    const hex = /^#[0-9a-f]{6}$/i.test(group.color || "") ? group.color : palette[index%palette.length];
    const numbers = hex.slice(1).match(/../g).map((part) => parseInt(part,16));
    const bright = numbers.map((n) => Math.min(240, Math.max(125, Math.round(n * .72 + 72))));
    return {color:`rgb(${bright.join(",")})`,bg:`rgba(${bright.join(",")},0.16)`,border:`rgba(${bright.join(",")},0.52)`,ink:`rgb(${bright.map((n)=>Math.min(245,Math.round(n*.78+42))).join(",")})`};
  }
  function laneStyles(element, group, index) { const colors=color(group,index); for (const [name,value] of Object.entries(colors)) element.style.setProperty(`--lane-${name}`,value); }
  function groupOf(node) { for (const id of list(node.group_ids)) { const group = state.groups.find((item) => item.id === id); if (group) return group; } return state.groups.at(-1); }
  function focusAnchor(node) { const focus=state.focus; if(!focus) return false; if(focus.type === "node") return String(node.id) === String(focus.id); if(focus.type === "year") return Number(node.year || String(node.date||"").slice(0,4)) === focus.year; if(focus.type === "group") return list(node.group_ids).some((id)=>String(id)===String(focus.id)); return false; }
  function focusMatchesNode(node) { if(!state.focus || !node) return true; if(focusAnchor(node)) return true; return list(state.snapshot?.edges).some((edge)=>edge.status !== "rejected" && ((String(edge.source)===String(node.id) && state.snapshot.nodes.some((item)=>String(item.id)===String(edge.target) && focusAnchor(item))) || (String(edge.target)===String(node.id) && state.snapshot.nodes.some((item)=>String(item.id)===String(edge.source) && focusAnchor(item))))); }
  function applyFocusClasses() { document.querySelectorAll(".paper-card").forEach((card)=>{ const node=state.snapshot?.nodes?.find((item)=>String(item.id)===String(card.dataset.nodeId)); card.classList.toggle("focus-dim", !!state.focus && !focusMatchesNode(node)); card.classList.toggle("focus-neighbor", !!state.focus && !focusAnchor(node) && focusMatchesNode(node)); }); document.querySelectorAll(".group-head").forEach((head)=>{const active=state.focus?.type === "group" && String(head.dataset.groupId)===String(state.focus.id); head.classList.toggle("focus-active",active); head.setAttribute("aria-pressed",String(active));}); document.querySelectorAll(".year-label").forEach((label)=>{const active=state.focus?.type === "year" && String(label.dataset.year)===String(state.focus.id); label.classList.toggle("focus-active",active); label.setAttribute("aria-pressed",String(active));}); queueEdges(); }
  function setFocus(focus) { const same = state.focus && focus && state.focus.type === focus.type && String(state.focus.id) === String(focus.id); state.focus = focus?.type === "node" ? focus : same ? null : focus; if (focus?.type !== "node") { state.selected = null; renderSelection(); } applyFocusClasses(); }
  function clearFocus() { state.focus=null; applyFocusClasses(); }
  function renderSnapshot(snapshot) {
    const languageBoundary=$("language-boundary"); if(languageBoundary) languageBoundary.hidden = !snapshot.language || snapshot.language === preferredLanguage;
    const effectiveId = state.snapshotDraft ? "__working__" : snapshot.id; const snapshotChanged = state.snapshotId !== effectiveId; if (snapshotChanged) { state.overviewFit = false; state.zoom = 1; state.focus = null; }
    state.snapshot = snapshot; state.snapshotId = effectiveId;
    state.groups = list(snapshot.groups).map((group) => ({...group}));
    const nodes = list(snapshot.nodes); if (!state.groups.length || nodes.some((node) => !state.groups.some((group) => list(node.group_ids).includes(group.id)))) state.groups.push({id:"__ungrouped",label:"Emerging connections",description:"Work awaiting a supported intent grouping."});
    $("empty-state").hidden = true; $("map-pane").hidden = false; $("inspector").hidden = false; $("map-toolbar").hidden = false;
    const mapWidth = Math.max(180, ($("map-pane")?.clientWidth || window.innerWidth || 800) - 62); const planned = window.DeepAnalyzeLayout?.plan ? window.DeepAnalyzeLayout.plan(snapshot, state.groups, {availableWidth: mapWidth, minCardWidth: 200, gap: 32}) : null;
    if (planned) state.groups = planned.groups; $("mode-badge").hidden = !snapshot.demo && state.run?.mode !== "demo";
    const timeline = $("timeline"); timeline.replaceChildren(); timeline.style.setProperty("--lane-count", state.groups.length);
    const laneTemplate = state.groups.map((group) => `${Math.max(200, Number(group.width) || 200)}px`).join(" "); timeline.style.setProperty("--lane-template", laneTemplate); timeline.style.setProperty("--card-width", `${planned?.cardWidth || 200}px`);
    const header = el("div", "timeline-header"); header.append(el("div", "year-head", ui("YEAR"))); state.groups.forEach((group,index) => { const head=el("div","group-head"); head.dataset.groupId=group.id; head.setAttribute("role","button"); head.setAttribute("tabindex","0"); laneStyles(head,group,index); head.style.minWidth=`${Math.max(200,Number(group.width)||200)}px`; head.append(el("h3","",group.label)); if(group.explanation_quality?.status === "incomplete") head.append(el("span","provisional-badge",ui("Synthesis incomplete"))); head.append(el("p","",group.description||"Shared technical intent")); head.addEventListener("click",()=>setFocus({type:"group",id:group.id})); head.addEventListener("keydown",(event)=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();setFocus({type:"group",id:group.id});}}); header.append(head); }); timeline.append(header);
    const byId = new Map(nodes.map((node) => [String(node.id), node]));
    const yearOf = (node) => Number(node.year || String(node.date||"").slice(0,4)) || null;
    const rows = planned?.rows || [...new Set(nodes.map(yearOf))].sort((a,b)=>a===null?1:b===null?-1:a-b).map((year)=>({year,cells:Object.fromEntries(state.groups.map((group)=>[group.id,[nodes.filter((node)=>yearOf(node)===year&&groupOf(node).id===group.id).map((node)=>String(node.id))]]))}));
    for (const rowPlan of rows) { const row=el("div","time-row"); const yearLabel=el("button","year-label",rowPlan.year===null?ui("Undated"):rowPlan.year); yearLabel.type="button"; yearLabel.dataset.year=String(rowPlan.year); yearLabel.addEventListener("click",()=>{if(rowPlan.year!==null)setFocus({type:"year",id:rowPlan.year,year:rowPlan.year});}); row.addEventListener("click",(event)=>{if(rowPlan.year!==null && !event.target.closest("button, a, .edge-hit"))setFocus({type:"year",id:rowPlan.year,year:rowPlan.year});}); row.append(yearLabel); state.groups.forEach((group,index)=>{ const cell=el("div","lane-cell"); laneStyles(cell,group,index); const subrows=rowPlan.cells?.[group.id] || []; for (const ids of subrows) { const subrow=el("div","lane-subrow"); for (const id of ids) { const node=byId.get(String(id)); if (node) { const card=paperCard(node,group,index); card.style.marginTop=`${planned?.offsets?.[String(id)] || 0}px`; subrow.append(card); } } if (subrow.childElementCount) cell.append(subrow); } row.append(cell); }); timeline.append(row); }
    if (!nodes.length) timeline.append(el("div","graph-wait",ui("This iteration has no included papers. Review its gaps and activity.")));
    const metrics=snapshot.metrics||{}; const knowledge=metrics.knowledge_depth; $("map-metrics").textContent=`${metrics.node_count??nodes.length} ${ui("papers")} · ${metrics.edge_count??list(snapshot.edges).length} ${ui("connections")} · ${ui(knowledge == null ? "depth" : "Knowledge depth")} ${knowledge ?? metrics.depth ?? 0}`;
    renderVersionControl(); renderRunActions(); renderSelection(); applyFocusClasses(); if (snapshotChanged) applyZoom(1, false); else queueEdges();
  }
function isKnowledgeSnapshot(snapshot=state.snapshot) { return snapshot?.groups?.some((group)=>group?.explanation_model === "knowledge_transitions_v1"); }
  Object.assign(translations.zh,{"Previous understanding":"此前的认识","Revised understanding":"这次改变的认识","evidence_linked":"证据已关联","incomplete":"尚未完成","invalid_stage_attachment":"阶段归属缺少双方证据","missing_research_assessment":"缺少问题解决程度评估","missing_knowledge_transition":"缺少明确的认识转折","incremental_work_on_spine":"局部改进不应增加主干深度","missing_research_role":"缺少论文作用或删除检验","invalid_stage_root":"阶段起点无效","redundant_knowledge_transition":"重复的认识转折"});
  function memberSupportFor(node, groupId=null) {
    const id=String(node?.id||"");
    return state.groups.filter(group=>!groupId || group.id===groupId).flatMap((group)=>list(group.member_support)).find((support)=>String(support?.paper_id||"")===id) || null;
  }
  function reviewLabel(review) {
    const status=typeof review === "string" ? review : review?.status;
    return status === "supported" || status === "reviewed" || status === "approved" ? "Supported transition" : "Unreviewed transition";
  }
  function paperCard(node, group, index) {
    const card=el("button","paper-card");card.type="button";card.dataset.nodeId=node.id; card.dataset.year=String(node.year || String(node.date||"").slice(0,4));card.setAttribute("aria-label",`${nodeName(node)}. ${text(node.solves||node.problem)}`);card.title=node.title||nodeName(node);laneStyles(card,group,index);
    const top=el("div","card-top");top.append(el("h4","",nodeName(node)));if(node.id===state.snapshot.seed_id)top.append(el("span","seed-badge",ui("SEED"))); if(node.context_role === "background") top.append(el("span","context-badge",ui("Background"))); const support=memberSupportFor(node,group.id); if(support?.role) top.append(el("span","role-badge",ui(support.role))); card.append(top,el("p","card-problem",node.solves||node.problem||"Problem connection has not yet been established."));
    const affiliations=list(node.affiliations);const orgs=el("div","card-affiliations");
    if(affiliations.length)for(const affiliation of affiliations){const item=el("span","affiliation",text(affiliation));orgs.append(item);}else orgs.append(el("span","affiliation",ui("Affiliation not established")));card.append(orgs);
    const extras=list(node.group_ids).filter((id)=>id!==group.id);if(extras.length){const pills=el("div","card-groups");for(const id of extras){const extra=state.groups.find((g)=>g.id===id);if(extra){const pill=el("span","group-pill",extra.label);const colors=color(extra,state.groups.indexOf(extra));pill.style.setProperty("--pill-bg",colors.bg);pill.style.setProperty("--pill-ink",colors.ink);pills.append(pill);}}card.append(pills);}
    card.addEventListener("click",()=>{setFocus({type:"node",id:node.id});state.selected={type:"node",id:node.id};renderSelection();});return card;
  }
  function section(container,title,contents) {
    if(contents==null || (Array.isArray(contents)&&!contents.length) || contents==="")return;
    const block=el("section","detail-section");block.append(el("h3","",ui(title)));
    if(Array.isArray(contents)){const ul=el("ul");for(const item of contents)ul.append(el("li","",text(item)));block.append(ul);}else block.append(el("p","",text(contents)));container.append(block);return block;
  }
  function detailLink(container,url,label){const safe=safeURL(url);if(!safe)return;const link=el("a","detail-source-link",ui(label));link.href=safe;link.target="_blank";link.rel="noopener noreferrer";container.append(link);}
  function appendEvidence(container,evidence){
    const synthetic = !!state.snapshot?.demo || state.run?.mode === "demo";
    if(!evidence.length){section(container,"Evidence",ui("No source excerpts are attached to this item."));return;}
    const block=el("section","detail-section");block.append(el("h3","",ui(synthetic?"Illustrative source material":"Source evidence")));
    for(const item of evidence){const box=el("div","evidence-item");box.append(el("div","evidence-state",ui(synthetic?"Synthetic example excerpt · not research evidence":item.verified?"Excerpt verified against retrieved source":"Excerpt not independently verified")));box.append(el("blockquote","",item.quote||"No quoted passage attached."));const meta=el("div","evidence-meta");meta.append(el("span","",item.location||"Location unspecified"));const url=safeURL(item.source_url);if(url){const link=el("a","",ui("Open source ↗"));link.href=url;link.target="_blank";link.rel="noopener noreferrer";meta.append(link);}box.append(meta);block.append(box);}
    block.append(el("p","quiet-note",ui(synthetic?"These excerpts are invented demonstration material, not retrieved publications or scientific evidence.":"A verified excerpt establishes attribution, not the truth of a scientific claim.")));container.append(block);
  }
  function renderSelection(){
    if(!state.snapshot)return;
    const selectionKey = `${state.run?.id || ""}:${state.snapshot?.id || ""}:${state.selected?.type || "overview"}:${state.selected?.id || ""}`;
    const inspectorContent = $("inspector-content");
    const selectionChanged = state.lastInspectorKey !== selectionKey;
    state.lastInspectorKey = selectionKey;
    document.querySelectorAll(".paper-card").forEach((card)=>{const selected=state.selected?.type==="node"&&card.dataset.nodeId===state.selected.id;card.classList.toggle("selected",selected);card.setAttribute("aria-pressed",String(selected));});
    const content=$("inspector-content");content.replaceChildren();
    const selection=state.selected;
    if(selection?.type==="node"){
      const node=state.snapshot.nodes.find((item)=>item.id===selection.id);if(!node){state.selected=null;renderSelection();return;}
      $("inspector-type").textContent=ui("PAPER DETAIL");content.append(el("h2","",nodeName(node)));if(node.title!==nodeName(node))content.append(el("p","detail-full-title",node.title));
      const meta=el("div","detail-meta");meta.append(el("span","",node.year||ui("Date unknown")),el("span","detail-badge",nice(node.source_status||"Source status unknown")));content.append(meta);
      const assessment=node.research_assessment||{}; const support=memberSupportFor(node);
      if((assessment.claimed_problem || assessment.demonstrated_result || assessment.outcome || assessment.conditions || assessment.unresolved)) {
        const outcome=assessment.outcome ? `${ui("outcome "+assessment.outcome)}` : "";
        section(content,"Stated outcome",assessment.claimed_problem);
        section(content,"Demonstrated outcome",[assessment.demonstrated_result, outcome].filter(Boolean).join(" · "));
        section(content,"Conditions",assessment.conditions);
        section(content,"Unresolved",assessment.unresolved);
      }
      if(isKnowledgeSnapshot() && support) {
        section(content,"Role",ui(support.role));
        const anchor=state.snapshot.nodes.find(item=>String(item.id)===String(support.stage_anchor_id));
        section(content,"Stage anchor",anchor ? nodeName(anchor) : support.stage_anchor_id);
        section(content,"Knowledge change",support.knowledge_change);
        section(content,"Removal effect",support.removal_effect);
        if(list(support.evidence_ids).length || list(support.attachment_evidence_ids).length) section(content,"Evidence",[...list(support.evidence_ids),...list(support.attachment_evidence_ids)].join(", "));
      }
      if(list(node.authors).length)content.append(el("p","detail-full-title",list(node.authors).map(text).join(", ")));
      if(list(node.affiliations).length)content.append(el("p","detail-full-title",list(node.affiliations).map(text).join(" · ")));
      const citationLinks=list(node.citation_links); if(citationLinks.length){ const provenance=citationLinks.map((link)=>{const anchor=state.snapshot.nodes.find((item)=>String(item.id)===String(link.anchor_id)); const anchorLabel=anchor ? nodeName(anchor) : (link.anchor_id || ui("Related")); return `${ui(link.direction === "cited_by_anchor" ? "Cited by mainline paper" : "Cites mainline paper")} · ${ui("Anchor")}: ${anchorLabel}`;}); section(content,"Citation provenance",provenance); for(const link of citationLinks){ if(link.source_url) detailLink(content,link.source_url,"Open citation source ↗"); } }
      const rationales=list(state.snapshot.discovery?.candidate_rationales || state.snapshot.candidate_rationales).filter((item)=>String(item.paper_id||"")===String(node.id)); if(rationales.length){ for(const rationale of rationales){ const anchor=state.snapshot.nodes.find((item)=>String(item.id)===String(rationale.anchor_id)); const anchorLabel=anchor ? nodeName(anchor) : rationale.anchor_id; const relationNames={same_problem:"Same problem",mechanism_consequence:"Mechanism consequence",necessary_background:"Necessary background",shared_domain_only:"Shared domain only",uncertain:"Uncertain"}; const details=[anchorLabel && `${ui("Anchor")}: ${anchorLabel}`, rationale.problem_relation && `${ui("Problem relation")}: ${ui(relationNames[rationale.problem_relation] || "Uncertain")}`, rationale.current_claim && `${ui("Current claim")}: ${rationale.current_claim}`, rationale.different_story && `${ui("Different story")}: ${rationale.different_story}`, rationale.selection_reason && `${ui("Selection reason")}: ${rationale.selection_reason}`].filter(Boolean); section(content,"Candidate rationale",details); } }
      const observationKinds={claimed_problem:"claimed_problem",demonstrated_gain:"demonstrated_gain",evaluation_protocol:"evaluation_protocol",limitation:"limitation",positioning:"positioning"}; const observationBasis={author_claim:"author_claim",reported_experiment:"reported_experiment",model_inference:"model_inference",unknown:"unknown"}; const observations=list(node.research_observations).filter(item=>item && item.statement && observationKinds[item.kind]); if(observations.length){ const details=observations.map(item=>`${ui(observationKinds[item.kind])} · ${ui(observationBasis[item.basis]||"unknown")}: ${item.statement}${list(item.evidence_ids).length ? ` · ${ui("Evidence")}: ${list(item.evidence_ids).join(", ")}` : ""}`); section(content,"Research observations",details); }
      detailLink(content,node.url,"Read the original paper ↗");
      if(node.solves)content.append(el("div","detail-callout",node.solves));
      if (node.context_reason) section(content, "Context role", `${ui("Background")}: ${node.context_reason}`); section(content,"Problem addressed",node.problem);section(content,"Change in mechanism",node.mechanism);section(content,"Results and consequences",node.results);section(content,"Limitations",node.limitations);section(content,"Assumptions & conditions",node.assumptions);section(content,"Uncertainty",node.uncertainties);
      section(content,"Discovered intent",list(node.group_ids).map((id)=>state.groups.find((group)=>group.id===id)?.label||id));
      const comparisons=list(state.snapshot.comparisons).filter((item)=>item.source===node.id||item.target===node.id);
      if(comparisons.length){const block=el("section","detail-section");block.append(el("h3","",ui("Compare underlying problems")));for(const comparison of comparisons){const other=state.snapshot.nodes.find((item)=>item.id===(comparison.source===node.id?comparison.target:comparison.source));const button=el("button","relationship-button",`${ui("Compare with")} ${nodeName(other)}`);button.type="button";button.append(el("small","",`${nice(comparison.relation)} · ${nice(comparison.group_action)}`));button.addEventListener("click",()=>{state.selected={type:"comparison",id:comparison.id};clearFocus();renderSelection();});block.append(button);}content.append(block);}
      const edges=list(state.snapshot.edges).filter((edge)=>edge.source===node.id||edge.target===node.id);if(edges.length){const block=el("section","detail-section");block.append(el("h3","",ui("Connected work")));for(const edge of edges){const outgoing=edge.source===node.id;const other=state.snapshot.nodes.find((item)=>item.id===(outgoing?edge.target:edge.source));const button=el("button","relationship-button",`${outgoing?"→":"←"} ${nodeName(other)}`);button.type="button";button.append(el("small","",`${nice(edge.kind)} · ${nice(edge.status)}`));button.addEventListener("click",()=>{state.selected={type:"edge",id:edge.id};clearFocus();renderSelection();});block.append(button);}content.append(block);}
      appendEvidence(content,list(node.evidence));section(content,"Revision history",list(state.snapshot.changes).filter((change)=>change.target_id===node.id).map((change)=>`${nice(change.kind)}: ${change.reason}`));if(node.added_iteration!=null)section(content,"First included",`${ui("Iteration")} ${node.added_iteration}`);
    }else if(selection?.type==="comparison"){
      const comparison=list(state.snapshot.comparisons).find((item)=>item.id===selection.id);if(!comparison){state.selected=null;renderSelection();return;}
      const source=state.snapshot.nodes.find((node)=>node.id===comparison.source),target=state.snapshot.nodes.find((node)=>node.id===comparison.target);
      $("inspector-type").textContent=ui("CROSS-PAPER COMPARISON");content.append(el("h2","",`${nodeName(source)} / ${nodeName(target)}`));
      content.append(el("p","detail-full-title",`${nice(comparison.relation)} · ${nice(comparison.group_action)}`));
      section(content,"Shared problem",comparison.shared_problem);section(content,"Earlier limitation",comparison.earlier_limitation);section(content,"What the later work changes",comparison.later_change);section(content,"Remaining gap",comparison.remaining_gap);section(content,"Grouping rationale",comparison.rationale);
      const ids=new Set(list(comparison.evidence_ids));appendEvidence(content,list(state.snapshot.nodes).flatMap((node)=>list(node.evidence)).filter((item)=>ids.has(item.id)));
      section(content,"Evidence boundary",ui(comparison.grounded?"Both papers have matching source excerpts. This is a proposed technical comparison; quotation matching does not prove the interpretation or historical influence.":"Evidence from both papers has not been established. This comparison remains uncertain."));
    }else if(selection?.type==="edge"){
      const edge=list(state.snapshot.edges).find((item)=>item.id===selection.id);if(!edge){state.selected=null;renderSelection();return;}
      const source=state.snapshot.nodes.find((node)=>node.id===edge.source),target=state.snapshot.nodes.find((node)=>node.id===edge.target);
      $("inspector-type").textContent=ui("CONNECTION DETAIL");content.append(el("h2","",`${nodeName(source)} → ${nodeName(target)}`));const meta=el("div","detail-meta");meta.append(el("span",`detail-badge ${edge.status||"hypothesis"}`,nice(edge.status||"hypothesis")),el("span","",nice(edge.kind)));content.append(meta);
      section(content,"Earlier problem",edge.problem);section(content,"How the later work responds",edge.mechanism);section(content,"Consequence",edge.consequence);section(content,"Reason for this connection",edge.rationale);section(content,"Conditions",edge.conditions);
      const ids=new Set(list(edge.evidence_ids));const evidence=list(state.snapshot.nodes).flatMap((node)=>list(node.evidence)).filter((item)=>ids.has(item.id));appendEvidence(content,evidence);
      const block=el("section","detail-section");block.append(el("h3","",ui("Papers")));for(const node of [source,target].filter(Boolean)){const button=el("button","relationship-button",nodeName(node));button.type="button";button.addEventListener("click",()=>{state.selected={type:"node",id:node.id};setFocus({type:"node",id:node.id});renderSelection();});block.append(button);}content.append(block);
      section(content,"Revision history",list(state.snapshot.changes).filter((change)=>change.target_id===edge.id).map((change)=>`${nice(change.kind)}: ${change.reason}`));
    }else{
      $("inspector-type").textContent=ui("EXPLORATION NOTES");content.append(el("h2","",ui("The shape of the question")));content.append(el("p","detail-full-title",`${ui("Iteration")} ${state.snapshot.iteration??"–"} · ${shortDate(state.snapshot.created_at)}`));
      if(state.snapshot.demo||state.run?.mode==="demo")content.append(el("div","detail-callout",ui("Illustrative demonstration. This tree uses synthetic examples to show the workflow; it is not a verified literature review.")));
      const metrics=state.snapshot.metrics||{};const stats=el("div","overview-stat-grid");for(const [value,label] of [[metrics.knowledge_depth??metrics.depth??0,metrics.knowledge_depth == null ? "SUPPORTED DEPTH" : "Knowledge depth"],[list(state.snapshot.nodes).length,"INCLUDED PAPERS"],[metrics.supported_edges||0,"SUPPORTED LINKS"],[list(state.snapshot.gaps).length,"OPEN QUESTIONS"]]){const stat=el("div","overview-stat");stat.append(el("strong","",value),el("span","",ui(label)));stats.append(stat);}content.append(stats);
      if (state.snapshotDraft) { content.append(el("div","detail-callout",ui("This is a working draft; it is not a completed iteration and cannot be exported or branched."))); const quality=state.snapshot.synthesis_quality||{}; const diagnostics=list(quality.group_diagnostics); const titleFor=(id)=>{const node=list(state.snapshot.nodes).find(item=>String(item.id)===String(id));return node?.title||node?.short_name||id;}; const groupLabel=(id)=>state.groups.find(group=>String(group.id)===String(id))?.label||id; const rows=[...list(quality.missing_source_ids).map(id=>`${ui("Missing source connections")}: ${titleFor(id)}`), ...list(quality.unconnected_source_ids).map(id=>`${ui("Unconnected papers")}: ${titleFor(id)}`), ...diagnostics.flatMap(item=>list(item.issues).slice(0,4).map(issue=>`${groupLabel(item.group_id)}: ${ui(issue)}`))]; if(rows.length) section(content,"Completion diagnostics",rows); } section(content,"Research scope",state.snapshot.scope); if(state.snapshot.discovery?.mode === "mainline_citations") section(content,"Citation boundary",ui("Candidate boundary: papers that directly cite, or are cited by, the seed or papers integrated into the evolving mainline. Different explanations are valuable; a candidate becomes an anchor only after grounded integration.")); for (const group of state.groups.filter((item) => item.id !== "__ungrouped" && item.explanation_model !== "knowledge_transitions_v1")) { const claim=group.explanatory_claim||{}; const quality=group.explanation_quality||{}; const details=[group.core_concept && `${ui("Core concept")}: ${group.core_concept}`, claim.constraint && `${ui("Constraint")}: ${claim.constraint}`, claim.mechanism && `${ui("Mechanism")}: ${claim.mechanism}`, claim.consequence && `${ui("Consequence")}: ${claim.consequence}`, quality.unexplained_member_ids?.length && `${ui("Unexplained members")}: ${quality.unexplained_member_ids.length}`, ...list(quality.issues).slice(0,3).map((issue)=>`${ui("Quality notes")}: ${ui(issue)}`), (!group.core_concept && !claim.constraint && !claim.mechanism && !claim.consequence) && (group.common_problem && `${ui("Common problem")}: ${group.common_problem}`), (!group.core_concept && !claim.constraint && !claim.mechanism && !claim.consequence) && (group.progression && `${ui("Progression")}: ${group.progression}`), (!group.core_concept && !claim.constraint && !claim.mechanism && !claim.consequence) && (group.open_problem && `${ui("Open problem")}: ${group.open_problem}`)].filter(Boolean); if (details.length) section(content, group.label || "Intent group", details); } if (isKnowledgeSnapshot()) {
        for (const group of state.groups.filter((item)=>item.id !== "__ungrouped")) {
          const spine=list(group.spine);
          const byId=new Map(list(state.snapshot.nodes).map((node)=>[String(node.id),node]));
          const transitions=spine.map((edge)=>{
            const source=byId.get(String(edge.source)), target=byId.get(String(edge.target));
            const names=`${source?nodeName(source):edge.source} → ${target?nodeName(target):edge.target}`;
            const relation=list(state.snapshot.edges).find(item=>item.source===edge.source && item.target===edge.target && ["addresses","builds_on","challenges"].includes(item.kind));
            const approved=group.semantic_review?.status==="supported" && group.explanation_quality?.status==="evidence_linked" && relation?.semantic_review?.status==="supported" && relation?.status==="supported";
            const review=approved ? "supported" : "pending";
            const parts=[names, edge.transition_type && ui(edge.transition_type), edge.claim_connection, edge.before && `${ui("Previous understanding")}: ${edge.before}`, edge.after && `${ui("Revised understanding")}: ${edge.after}`, ui(reviewLabel(review))].filter(Boolean);
            return parts.join(" · ");
          });
          const details=[group.progression && `${ui("Mainline progression")}: ${group.progression}`,group.open_problem && `${ui("Open problem")}: ${group.open_problem}`,group.semantic_review && `${ui("Semantic review")}: ${ui(reviewLabel(group.semantic_review))}`,group.explanation_quality && `${ui("Explanation quality")}: ${ui(group.explanation_quality.status || "incomplete")}`].filter(Boolean);
          if(details.length) section(content,group.label || "Intent group",details);
          if(transitions.length) section(content,"Mainline progression",transitions);
        }
      }
      const coverage=list(state.snapshot.discovery?.year_coverage); if(coverage.length){ const order=list(state.snapshot.discovery?.year_order); const byYear=new Map(coverage.map((item)=>[Number(item.year),item])); const rows=(order.length?order:coverage.map((item)=>item.year)).map((year)=>byYear.get(Number(year))).filter(Boolean).map((item)=>`${item.year}: ${item.candidates??0} ${ui("candidates")}, ${item.read??0} ${ui("read")}, ${item.included??0} ${ui("included")} · ${ui(item.pool_status||"")}`); section(content,"Annual coverage",rows); if(coverage.some((item)=>item.pool_status === "pending_scan")) section(content,"Annual coverage",ui("Not all papers in a year were scanned; this does not mean no other papers exist.")); } section(content,"How to read this map",ui("Time runs downward. Colored columns group discovered intent; cross-column links preserve shared mechanisms. Select a paper or connection to inspect its evidence."));
      section(content,"Unresolved gaps",list(state.snapshot.gaps).map((gap)=>gap.description||text(gap))); const dispositions=list(state.snapshot.source_dispositions).filter((item)=>item.status && item.status !== "included"); if(dispositions.length) section(content,"Source dispositions",dispositions.map((item)=>`${ui(item.status)} · ${item.title || item.paper_id}${item.reason ? ` — ${item.reason}` : ""}`)); section(content,"Changes in this iteration",list(state.snapshot.changes).map((change)=>`${nice(change.kind)} · ${change.reason||change.target_id}`));section(content,"Review notes",state.snapshot.review_notes);
      section(content,"About depth",ui("Depth counts supported, chronological problem transitions. Additional papers, layout rows, and hypotheses do not by themselves make an explanation deeper."));
    }
    if (selectionChanged && inspectorContent) inspectorContent.scrollTop = 0;
    queueEdges();
  }
  function applyZoom(value, manual = true) { if (manual) state.overviewFit = false; state.zoom = Math.max(.2, Math.min(2.5, Number(value) || 1)); const stage = $("graph-stage"); if (!stage) return; stage.style.zoom = String(state.zoom); $("zoom-label").textContent = `${Math.round(state.zoom * 100)}%`; queueEdges(); }
  function fitZoom() { const scroll = $("graph-scroll"), timeline = $("timeline"); if (!scroll || !timeline || !timeline.childElementCount) return; const naturalWidth = Math.max(1, timeline.scrollWidth), availableWidth = Math.max(1, scroll.clientWidth - 24); applyZoom(Math.max(.2, Math.min(1, availableWidth / naturalWidth)), false); }
  let edgeFrame=null;
  function queueEdges(){if(edgeFrame!=null)cancelAnimationFrame(edgeFrame);edgeFrame=requestAnimationFrame(()=>{edgeFrame=null;drawEdges();});}
  let edgeRouteCache = {key: "", routes: new Map()};
  function drawEdges(){
    const stage=$("graph-stage"),svg=$("connections");if(!state.snapshot||$("map-pane").hidden)return;const bounds=stage.getBoundingClientRect();const timeline=$("timeline");const scale=state.zoom||1;const width=Math.max(1,timeline.scrollWidth),height=Math.max(1,timeline.scrollHeight);svg.setAttribute("width",width);svg.setAttribute("height",height);svg.setAttribute("viewBox",`0 0 ${width} ${height}`);svg.replaceChildren();
    const ns="http://www.w3.org/2000/svg";const make=(tag,attrs)=>{const item=document.createElementNS(ns,tag);for(const [key,value]of Object.entries(attrs||{}))item.setAttribute(key,value);return item;};
    const defs=make("defs");for(const [id,fill] of [["supported-arrow","#8fd0b5"],["hypothesis-arrow","#c8b5e8"],["selected-arrow","#6fe0bf"]]){const marker=make("marker",{id,viewBox:"0 0 8 8",refX:"7",refY:"4",markerWidth:"5",markerHeight:"5",orient:"auto-start-reverse"});marker.append(make("path",{d:"M 0 1 L 7 4 L 0 7",fill:"none",stroke:fill,"stroke-width":"1.4"}));defs.append(marker);}svg.append(defs);
    const cards=new Map([...stage.querySelectorAll(".paper-card")].map((card)=>[card.dataset.nodeId,card]));
    const rects=[...cards.entries()].map(([id,card])=>{const r=card.getBoundingClientRect();return{id,left:(r.left-bounds.left)/scale,right:(r.right-bounds.left)/scale,top:(r.top-bounds.top)/scale,bottom:(r.bottom-bounds.top)/scale};});
    const byId=new Map(rects.map(r=>[r.id,r]));
    const edges=list(state.snapshot.edges).filter(e=>e.status!=="rejected"&&cards.has(e.source)&&cards.has(e.target)&&e.source!==e.target);
    const routeKey=JSON.stringify([state.snapshotId,width,height,rects.map(r=>[r.id,...[r.left,r.right,r.top,r.bottom].map(v=>Math.round(v*2)/2)]),edges.map(e=>[e.id,e.source,e.target])]);
    if(edgeRouteCache.key!==routeKey)edgeRouteCache={key:routeKey,routes:new Map()};
    const outgoing=new Map(), incoming=new Map(), usedTracks=new Map();
    for(const edge of edges){if(!outgoing.has(edge.source))outgoing.set(edge.source,[]);if(!incoming.has(edge.target))incoming.set(edge.target,[]);outgoing.get(edge.source).push(edge);incoming.get(edge.target).push(edge);}
    for(const values of outgoing.values())values.sort((a,b)=>byId.get(a.target).left-byId.get(b.target).left || String(a.id).localeCompare(String(b.id)));
    for(const values of incoming.values())values.sort((a,b)=>byId.get(a.source).left-byId.get(b.source).left || String(a.id).localeCompare(String(b.id)));
    for(const [index,edge] of edges.entries()){
      const source=cards.get(edge.source),target=cards.get(edge.target);
      const route=edgeRouteCache.routes.get(index) || window.DeepAnalyzeLayout.routeEdge(byId.get(edge.source),byId.get(edge.target),rects,{width,height,index,
        sourceSlot:outgoing.get(edge.source).indexOf(edge),sourceCount:outgoing.get(edge.source).length,
        targetSlot:incoming.get(edge.target).indexOf(edge),targetCount:incoming.get(edge.target).length,usedTracks});
      edgeRouteCache.routes.set(index,route);
      const path=route.path;
      const selected=state.selected?.type==="edge"&&state.selected.id===edge.id; const sourceNode=state.snapshot.nodes.find((item)=>String(item.id)===String(edge.source)), targetNode=state.snapshot.nodes.find((item)=>String(item.id)===String(edge.target)); const incident=!state.focus || focusAnchor(sourceNode) || focusAnchor(targetNode); const status=["supported","hypothesis","rejected"].includes(edge.status)?edge.status:"hypothesis";
      const visible=make("path",{d:path,"data-source":edge.source,"data-target":edge.target,"data-collisions":route.collisions,class:`edge-path ${status}${selected?" selected":""}${incident?"":" focus-dim"}`,style:`stroke:${selected?"#6fe0bf":status==="supported"?"#8fd0b5":status==="rejected"?"#d2a99d":"#c8b5e8"}`,"marker-end":`url(#${selected?"selected":status==="supported"?"supported":"hypothesis"}-arrow)`});
      const hit=make("path",{d:path,class:"edge-hit",tabindex:"0",role:"button","aria-label":`${nice(status)} connection: ${source.querySelector("h4").textContent} to ${target.querySelector("h4").textContent}`});const select=()=>{state.selected={type:"edge",id:edge.id};clearFocus();renderSelection();};hit.addEventListener("click",select);hit.addEventListener("keydown",(event)=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();select();}});svg.append(visible,hit);
    }
  }
  function schedulePoll(){if(state.timer)clearTimeout(state.timer);if(exported)return;if(state.activeRunId||active(state.run)||state.runs.some(active))state.timer=setTimeout(poll,2400);}
  async function poll(){if(state.polling)return;state.polling=true;try{
    await refreshState();if(state.run){const id=state.run.id;const run=await api(`/api/runs/${encodeURIComponent(id)}`);if(state.run?.id===id){state.run=run;renderRun();if(state.followLatest){const newest=typeof run.latest_snapshot==="object"?run.latest_snapshot?.id:run.latest_snapshot||run.snapshots?.at(-1)?.id;if(newest&&newest!==state.snapshotId&&state.followLatest)await showLatest(); else if(!newest&&run.working_snapshot&&Array.isArray(run.working_snapshot.nodes)){state.snapshotDraft=true;state.snapshotId="__working__";renderSnapshot(run.working_snapshot);}}renderRuns();}}
  }catch(error){notice(`Connection interrupted: ${error.message}`,true);}finally{state.polling=false;schedulePoll();}}
  function renderAuth() {
    const result = state.auth; if (!result) return;
    $("auth-label").textContent = ui(result.authenticated ? "Connected" : "Connect Codex");
    $("auth-state").textContent = !result.available ? ui("Codex runtime not found. Install the Codex CLI to enable live research.") : result.authenticated ? ui(result.mode === "apiKey" || result.mode === "api_key" ? "Connected through an API key." : "Connected through your local Codex session.") : ui(result.error || "Codex is available. Sign in to begin live research.");
    $("auth-logout").hidden = !result.authenticated;
    $("chatgpt-login").disabled = !result.available; $("api-login").disabled = !result.available;
  }
  async function refreshAuth(){
    try { state.auth = await api("/api/auth/status"); renderAuth(); }
    catch(error) { $("auth-state").textContent = ui(error.message); }
  }
  async function authAction(action){$("auth-error").hidden=true;for(const id of ["chatgpt-login","api-login","auth-logout"])$(id).disabled=true;try{await action();}catch(error){$("auth-error").textContent=error.message;$("auth-error").hidden=false;}finally{await refreshAuth();}}
  function showLogin(result){
    const box=$("login-result");box.replaceChildren();const url=safeURL(result.auth_url||result.authUrl||result.url||result.login_url||result.verification_uri||result.verification_url);const code=result.user_code||result.userCode||result.code;
    if(result.authenticated){box.append(el("p","",ui("Connected. You can close this window and start an exploration.")));}
    else if(url){const link=el("a","button button-outlined full-width",ui("Continue in your browser ↗"));link.href=url;link.target="_blank";link.rel="noopener noreferrer";box.append(link);if(code){box.append(el("p","",ui("Enter this code if requested:")),el("code","",code));}box.append(el("p","",ui("After signing in, select “Check connection” below.")));}
    else box.append(el("p","",result.message||"Login started. Follow the local Codex sign-in instructions, then check the connection."));box.hidden=false;
  }
  function bind(){

    $("notice-dismiss").addEventListener("click",dismissNotice); $("trash-empty").addEventListener("click",openTrashPurge); $("trash-purge-dialog").querySelector(".button[value=cancel]").addEventListener("click",()=>$("trash-purge-dialog").close()); $("trash-purge-dialog").addEventListener("close",()=>{state.trashPurgeIds=[];}); $("trash-purge-confirm").addEventListener("click",(event)=>{event.preventDefault();withAction(purgeTrash);});
    $("sidebar-toggle").title=ui("Toggle sidebar"); $("sidebar-toggle").addEventListener("click",()=>setSidebarCollapsed(!state.sidebarCollapsed)); try{state.sidebarCollapsed=localStorage.getItem("deepanalyze-sidebar-collapsed")==="1";}catch{} setSidebarCollapsed(state.sidebarCollapsed);
    $("language-select").addEventListener("change", (event) => { preferredLanguage = event.target.value === "en" ? "en" : "zh"; try { localStorage.setItem("deepanalyze-language", preferredLanguage); } catch {} applyLanguage(); });
    applyLanguage();
    $("budget-rounds").addEventListener("input",()=>{$("budget-summary").textContent=`${numeric("budget-rounds",10,1,20)} ${ui("rounds")}`;});
    $("start-button").addEventListener("click",()=>withAction(async()=>{const seed=$("seed-input").value.trim();if(!seed){$("seed-input").focus();throw new Error("Enter a paper title, DOI, or arXiv link to begin.");}if(!state.auth?.authenticated){$("auth-dialog").showModal();await refreshAuth();return;}const run=await api("/api/runs",{method:"POST",body:JSON.stringify({seed,mode:"live",config:config()})});await refreshState();await selectRun(run.id); }));
    $("demo-button").addEventListener("click",()=>withAction(async()=>{const run=await api("/api/runs",{method:"POST",body:JSON.stringify({seed:"Illustrative research evolution",mode:"demo",config:config()})});await refreshState();await selectRun(run.id);}));
    $("stop-button").addEventListener("click",()=>withAction(async()=>{if(!state.run)return;const run=await api(`/api/runs/${encodeURIComponent(state.run.id)}/stop`,{method:"POST",body:"{}"});if(run.id)state.run=run;else state.run=await api(`/api/runs/${encodeURIComponent(state.run.id)}`);renderRun();schedulePoll();}));
    $("resume-button").addEventListener("click",()=>withAction(async()=>{if(!state.run||!state.snapshotId)return;const resumeConfig=config(); const run=await api(`/api/runs/${encodeURIComponent(state.run.id)}/resume`,{method:"POST",body:JSON.stringify({snapshot_id:state.snapshotId, config:resumeConfig})});await refreshState();await selectRun(run.id);}));
    $("snapshot-select").addEventListener("change",()=>{const id=$("snapshot-select").value;const newest=state.run?.snapshots?.at(-1)?.id;loadSnapshot(id,id===newest).catch((error)=>notice(error.message,true));});
    $("retry-synthesis-button")?.addEventListener("click",()=>withAction(async()=>{if(!state.run?.id||!state.snapshotDraft)return;const next=await api(`/api/runs/${encodeURIComponent(state.run.id)}/retry-synthesis`,{method:"POST",body:"{}"});await refreshState();await selectRun(next.id);}));
    $("close-inspector").addEventListener("click",()=>{state.selected=null;clearFocus();renderSelection();});
    $("auth-button").addEventListener("click",()=>{$("auth-dialog").showModal();refreshAuth();});
    $("auth-refresh").addEventListener("click",refreshAuth);
    $("chatgpt-login").addEventListener("click",()=>authAction(async()=>{showLogin(await api("/api/auth/login",{method:"POST",body:JSON.stringify({method:"chatgpt"})}));}));
    $("api-login").addEventListener("click",()=>authAction(async()=>{const key=$("api-key").value.trim();$("api-key").value="";if(!key)throw new Error("Enter an API key first.");const result=await api("/api/auth/login",{method:"POST",body:JSON.stringify({method:"apiKey",api_key:key})});showLogin(result);}));
    $("auth-logout").addEventListener("click",()=>authAction(async()=>{await api("/api/auth/logout",{method:"POST",body:"{}"});$("login-result").hidden=true;}));
    $("auth-dialog").addEventListener("close",()=>{$("api-key").value="";});
    document.addEventListener("keydown",(event)=>{if(event.key==="Escape"&&!$("auth-dialog").open&&(state.selected||state.focus)){state.selected=null;clearFocus();renderSelection();}});
    $("zoom-out").addEventListener("click", () => applyZoom(state.zoom - .1)); $("zoom-in").addEventListener("click", () => applyZoom(state.zoom + .1)); $("zoom-reset").addEventListener("click", () => applyZoom(1)); $("zoom-fit").addEventListener("click", fitZoom); $("graph-scroll").addEventListener("wheel", (event) => { if (event.ctrlKey || event.metaKey) { event.preventDefault(); applyZoom(state.zoom + (event.deltaY < 0 ? .1 : -.1)); } }, {passive:false}); let lastMapWidth=0; const handleLayoutResize=()=>{const width=$("map-pane")?.clientWidth||0; if(state.snapshot && width && width!==lastMapWidth){lastMapWidth=width; renderSnapshot(state.snapshot);} else queueEdges();}; window.addEventListener("resize",handleLayoutResize); if(window.ResizeObserver){ const observer=new ResizeObserver(()=>handleLayoutResize()); observer.observe($("timeline")); observer.observe($("graph-scroll")); observer.observe($("map-pane")); }
    document.addEventListener("visibilitychange",()=>{if(!document.hidden&&!exported&&(state.activeRunId||active(state.run)||state.runs.some(active))){if(state.timer)clearTimeout(state.timer);poll();}});
  }
  async function initialize(){
    bind();
    if (!exported) window.setInterval(() => { const counter = $("elapsed-seconds"); if (counter && active(state.run)) counter.textContent = elapsedSeconds(state.run); }, 1000);
    if(exported){document.body.classList.add("export-mode");$("workspace-sidebar").hidden=true;$("sidebar-toggle").hidden=true;$("auth-button").hidden=true;$("environment-label").textContent=ui("Saved research snapshot");document.querySelector(".brand").removeAttribute("href");state.run=exported.run||{seed:"Research exploration",mode:exported.snapshot?.demo?"demo":"live"};state.followLatest=false;renderRun();renderSnapshot(exported.snapshot);$("run-progress").hidden=true;$("resume-button").hidden=true;$("export-button").hidden=true;return;}
    try{const result=await refreshState();await refreshAuth();const params=new URLSearchParams(location.search);const id=params.get("run")||result.active_run_id||state.runs[0]?.id;if(id){await selectRun(id);if(params.get("snapshot"))await loadSnapshot(params.get("snapshot"),false);}}catch(error){notice(`Could not load the local workspace: ${error.message}`,true);}
  }
  initialize();
})();
