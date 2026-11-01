export type GuideTopic = 'import'|'analysis'|'profile'|'plan'|'timetable'|'materials'|'knowledge'|'privacy';
export interface GuideStep {title:string;description:string}
export interface GuideChapter {
  id:GuideTopic;title:string;summary:string;scene:string;icon:string;
  steps:GuideStep[];result:string;notes:string[];action:{label:string;to:string};keywords:string[];
}
export interface GuideFaq {id:string;question:string;answer:string;topic:GuideTopic;keywords:string[]}

export const quickStart: {title:string;description:string;topic:GuideTopic}[] = [
  {title:'导入通知',description:'选择正文、公开链接或文件，核对后保存来源。',topic:'import'},
  {title:'核对结果',description:'查看原文依据，补充缺失附件与个人资料。',topic:'analysis'},
  {title:'确认行动',description:'选择正确日期与步骤，再确认生成行动步骤。',topic:'analysis'},
  {title:'开始执行',description:'更新任务状态，按课表预览并确认时间安排。',topic:'plan'},
];

export const guideChapters: GuideChapter[] = [
  {
    id:'import',title:'导入一份通知',summary:'文字、网页、文件和系统分享都从这里开始。',
    scene:'收到群聊通知、学校公告或报名文件，想整理成一件可跟进的事项。',icon:'/assets/icons/actions/icon_attach.svg',
    steps:[
      {title:'选择来源',description:'在工作台点击“导入并分析”。可粘贴正文、填写一个公开网页链接，或选择多个文件；同一件事的不同来源可以放在同一批次。事项标题选填。'},
      {title:'核对隐私并保存',description:'检查“准备保存的来源”和文字的本地隐私预览。人工核对图片、PDF、网页等尚未端侧扫描的内容，勾选确认后点击“保存并核对来源”。真实导入需要先登录。'},
      {title:'检查来源与附件',description:'在“确认导入来源”页查看每项处理结果。缺少正文时点击“补充来源”；发现网页附件候选时，核对链接后逐项点击“确认获取此附件”。发现链接不代表已经读取附件。'},
      {title:'开始分析',description:'确认有可用来源后点击“开始分析”。部分来源失败时，可以选择“开始部分分析”，也可以先补充来源。进入分析进度页后，点击“打开生成的事项”查看结果。'},
    ],
    result:'成功来源会合并为一个事项；失败来源保留原因。全部来源失败时，不会生成虚假的分析结果。',
    notes:[
      '支持 PDF、PNG/JPEG、TXT、HTML、DOCX、XLS/XLSX。单次最多选择 10 个文件；图片不超过 10 MB，其他文件不超过 20 MB；PDF 最多 20 页。',
      '需要登录或权限的网页可能读取失败。可以复制有权查看的正文，或下载文件后手动选择。旧版 .doc 请先转换为 DOCX 或 PDF。',
      '支持系统分享的移动端可从其他应用分享至知事，再核对待导入内容。浏览器中使用粘贴、链接和文件入口。',
      '已保存来源可从导入页的“继续”入口恢复；尚未保存的输入不等同于已保存批次。',
    ],action:{label:'去导入通知',to:'/imports/new'},keywords:['上传','文件','图片','Word','Excel','PDF','网页','链接','分享','批次','附件','格式','大小','失败'],
  },
  {
    id:'analysis',title:'读懂并确认解析结果',summary:'先看证据与缺失信息，再确认日期和行动步骤。',
    scene:'导入后已打开“解析结果”，需要知道哪些结果可用、哪些内容还需核对。',icon:'/assets/icons/actions/icon_search.svg',
    steps:[
      {title:'对照原通知',description:'先核对事项标题和“通知附件”。若提示附件缺失或读取失败，请补充上传；通过“用补充附件重新分析”更新分析后，仍需重新核对候选。'},
      {title:'理解相关性',description:'“相关”表示当前可计算的条件与已确认资料匹配；“不相关”表示存在不满足的条件；“待确认（UNKNOWN）”表示资料、证据或可计算条件不足。待确认不等于不符合，相关也不等于最终获批。'},
      {title:'核对日期候选',description:'在“核对分析候选”中区分发布信息、活动时间和截止候选。选择适用于当前事项的截止日期；年份、用途不清时先核对原文，也可以手工填写，或暂不设置。'},
      {title:'核对行动与依赖',description:'逐项检查行动步骤及其原文引用，取消不需要的建议步骤。必要时为不同步骤选择各自的截止日期；有明确前后依赖时，同时保留所需前置步骤。'},
      {title:'明确确认',description:'勾选“我已核对……”后点击“确认并生成行动步骤”。“查看依据”和“全部来源”可追溯到原文；“分析版本与重试”用于查看历史及重新分析。'},
    ],
    result:'确认后的行动步骤可在执行计划中查看。确认日期和步骤不会自动把“待确认”的资格判断变为“相关”。',
    notes:[
      '没有识别到有依据的步骤或材料时，页面会明确说明。不要把空结果理解成“不需要办理”，应继续核对原文。',
      '重新分析后，当前候选需要再次确认；历史快照用于追溯，不代表本次确认已完成。',
      '同一事项可能有报名、提交、活动等多个日期，不要直接把发布日期当作截止日期。',
    ],action:{label:'打开我的事项',to:'/cases'},keywords:['解析','结果','确认','核对','UNKNOWN','TRUE','FALSE','待确认','日期','截止','资格','证据','步骤','重试'],
  },
  {
    id:'profile',title:'补充个人资料',summary:'让通知条件与当前设备已确认的资料逐项对照。',
    scene:'结果提示缺少学院、年级、排名等资料，或资料存在冲突、过期。',icon:'/assets/icons/features/icon_个人画像.svg',
    steps:[
      {title:'打开个人画像',description:'在“我的”中进入“个人画像”，或在解析页点击“查看修改本机资料”。按实际情况填写通用资料，未知字段可以留空。'},
      {title:'设置范围与有效期',description:'选择“通用资料”或指定事项，并按需要填写资料有效期。例如只适用于某次申报的信息，应限定到对应事项。'},
      {title:'核对资料卡',description:'点击“保存画像”，核对生成的资料卡；从补充说明整理出的资料也需要逐项确认。修改后的资料须重新核对，未确认、过期或冲突的资料不会直接用于肯定判断。'},
      {title:'回到事项查看判断',description:'重新进入解析结果或相关性判断页，检查仍缺哪些字段。关注分类用于表达兴趣，不会覆盖通知中的硬性资格条件。'},
    ],
    result:'资料保存在当前设备的当前身份空间，判断使用已确认、未过期且适用于当前事项的资料。补充说明不会自动上传。',
    notes:[
      '本机体验资料与登录账户资料分别保存；换设备后不会自动出现同一份本机资料，可按需使用本机备份与恢复。',
      '同一字段有相互矛盾的资料时，应核对并修改相关资料卡；系统会将冲突字段按未知处理。',
      '退出登录会清除当前账户在本机的资料缓存，重要资料请提前使用页面中的备份功能。',
    ],action:{label:'打开个人画像',to:'/profile'},keywords:['画像','个人','资料','年级','学院','排名','冲突','过期','有效期','备份','恢复','本机'],
  },
  {
    id:'plan',title:'执行步骤与安排时间',summary:'跟进任务状态，先预览排程，再确认保存。',
    scene:'已经确认行动步骤，希望知道先做什么，并把任务放进空闲时间。',icon:'/assets/icons/actions/icon_calendar.svg',
    steps:[
      {title:'选择事项并查看步骤',description:'从底部“执行计划”进入，点击事项卡片切换要处理的事项。在行动步骤中查看顺序、原文依据与关联材料。'},
      {title:'更新执行状态',description:'根据实际进展将步骤设为待完成、进行中、已完成或已跳过。有前置条件的步骤应先核对其依赖；跳过前确认该步骤确实不需要执行。'},
      {title:'填写排程所需信息',description:'切换到“日程安排”，在“填写步骤耗时与拆分方式”中保存预计耗时等设置。检查本机课表、账户课程与忙碌时段，并设置本次排程的时间偏好。'},
      {title:'预览并核对',description:'使用本机课表参与账户排程时，先确认发送课表占用时段，再点击“预览任务排程”。检查建议时间与“未安排”原因，必要时调整耗时、日期、依赖或空闲时段。'},
      {title:'确认保存',description:'核对草稿后点击“确认整份排程”，并确认保存到账户。已有安排可点击编辑或锁定；数据变化导致草稿失效时，需要重新预览。'},
    ],
    result:'任务状态用于跟进进展；排程草稿只有经确认后才进入账户日程。预计耗时与安排都需要人工核对。',
    notes:[
      '缺少耗时、证据、可用时段，或前置步骤未满足时，任务可能无法安排。请按“未安排”原因处理。',
      '选择事项后才能为该事项预览任务排程；明确不相关的事项不会直接进入排程。',
      '离线样例可用于体验任务状态与本机课表预览；账户日程的读取和保存需要登录及后端连接。',
    ],action:{label:'打开执行计划',to:'/plan'},keywords:['任务','计划','状态','日程','排程','安排','时间','耗时','依赖','前置','锁定','未安排'],
  },
  {
    id:'timetable',title:'录入本机课表',summary:'确认课程、学期与单双周，让排程避开上课时间。',
    scene:'希望任务安排避开课程，或需要处理停课、临时调课。',icon:'/assets/icons/actions/icon_calendar.svg',
    steps:[
      {title:'检查学期日期',description:'从执行计划的“查看修改课表”进入“本机课表”，先核对本学期开始与结束日期。学期起始日会影响周次展开。'},
      {title:'手工录入或整理文字',description:'填写课程、星期、起止时间、周次与单双周，或粘贴类似“高等数学 周一 08:00-10:00 第1-18周”的文字进行整理。'},
      {title:'逐项确认候选',description:'对照真实课表核对整理出的课程候选。图片或 PDF 的文件解析需要登录并明确确认上传；无法确定的行请手工补充。'},
      {title:'处理变动并重新预览',description:'核对“已确认课程”和重叠提示。某次停课可取消对应日期；临时调课请另增课程。返回日程页重新预览任务安排。'},
    ],
    result:'已确认课表保存在当前设备，按北京时间及单双周展开。参与账户排程时，发送的是经确认的占用时段。',
    notes:['合成课表是演示数据，使用后应核对并移除与真实课表不符的课程。','课表内容发生变化后，旧排程草稿需要重新预览，已有账户日程也应人工核对。'],
    action:{label:'打开本机课表',to:'/timetable'},keywords:['课表','课程','学期','单双周','停课','调课','周次','离线'],
  },
  {
    id:'materials',title:'管理并关联材料',summary:'区分“需要准备的材料”与“已经上传的文件”。',
    scene:'通知要求提交申请表、证明等文件，希望统一保存并关联到事项或步骤。',icon:'/assets/icons/actions/icon_attach.svg',
    steps:[
      {title:'先看材料要求',description:'在解析结果中查看“材料要求”，点击“查看依据”核对原文。材料要求只是清单，不代表已经上传或提交。'},
      {title:'上传到材料库',description:'在工作台或“我的”打开“材料库”，登录后点击“上传”。选择文件，填写名称与分类，并人工核对隐私后确认上传。'},
      {title:'关联事项与步骤',description:'在材料表单中选择相关事项，按需关联具体步骤。已有文件可通过编辑更新名称、分类和关联关系。'},
      {title:'核对文件内容',description:'从材料库预览或查看文件，并在事项的“已关联文件”中检查关联结果。搜索名称或按分类筛选，可以快速找到材料。'},
    ],
    result:'文件和关联关系保存在当前账户中。上传、关联文件均不等于已经向通知要求的接收方提交材料。',
    notes:['需要提交到外部平台、邮箱或办公室的材料，仍须按正式通知自行完成提交。','补充通知原文附件应使用解析页的“通知附件”；个人申请材料则在“材料库”管理。'],
    action:{label:'打开材料库',to:'/vault'},keywords:['材料','文件','申请表','证明','关联','上传','提交','预览','附件'],
  },
  {
    id:'knowledge',title:'查询知识资料与规则依据',summary:'导入细则，检索可追溯的原文片段。',
    scene:'想查询学校细则、评奖办法或其他规则文件，并保留出处。',icon:'/assets/icons/actions/icon_search.svg',
    steps:[
      {title:'导入规则资料',description:'从“我的”进入“知识资料库”。登录后填写资料标题，粘贴正文或选择文件，核对隐私并确认后点击“导入知识资料”。'},
      {title:'检查索引结果',description:'在“已导入资料”中查看状态。索引未完成时按错误提示处理，不要将失败资料当作已可检索。'},
      {title:'查询来源片段',description:'在“查询校内规则”中输入关键词或问题，点击“查询来源片段”，查看匹配原文、来源片段编号和定位信息。'},
      {title:'对照实际事项',description:'回到具体事项的“规则依据”，对照通知与已有条款。检索结果和匹配分数帮助查找资料，仍需要核对适用范围及原文。'},
    ],
    result:'当前知识库使用本地检索与原文摘录。没有匹配来源时会明确说明，不会用演示资料代替你的账户资料。',
    notes:['本地检索不等于无需后端；账户知识资料的导入与查询仍需服务连接。','匹配分数不是资格结论，也不是正确率。删除索引不会自动删除原件或已关联的事项证据。'],
    action:{label:'打开知识资料库',to:'/knowledge'},keywords:['知识库','知识资料','规则','细则','检索','查询','来源','证据','索引'],
  },
  {
    id:'privacy',title:'检查隐私并安全分享',summary:'核对检测范围与脱敏结果，再选择是否分享。',
    scene:'需要上传通知、分享文本，或处理文件中可能存在的个人信息。',icon:'/assets/icons/actions/icon_search.svg',
    steps:[
      {title:'选择待检查内容',description:'在“我的”进入“隐私保护”，粘贴文字或选择 TXT 文件；也可从事项的“安全分享”入口带入第一条原文依据，先确认它是否覆盖需要分享的内容。'},
      {title:'开始检查',description:'点击“开始隐私检查”，查看身份证号、手机号、银行卡号等已支持格式的检测结果。姓名、地址、邮箱、学号及上下文仍需人工检查。'},
      {title:'逐项核对安全版本',description:'对照原文与脱敏版本。未发现已支持格式不代表绝对安全；有尚不能可靠遮盖的类型时，应先手工处理再检查。'},
      {title:'复制或分享',description:'生成可用安全版本后，使用页面中的复制或系统分享按钮。当前平台不支持系统分享时，可使用复制；接收对象由你在系统面板中选择。'},
    ],
    result:'仅在你操作后才复制或打开分享面板。隐私检测文本不写入个人画像、事项或检测历史；这与导入通知、上传材料的账户保存流程不同。',
    notes:['导入页的本地隐私预览不代表所有来源都已扫描，也不代表保存的所有原文都已被替换为脱敏文本。','文件的“文件隐私与脱敏”页可检查支持的文件并生成脱敏副本；不支持的格式或类型仍需人工处理。'],
    action:{label:'打开隐私保护',to:'/privacy'},keywords:['隐私','脱敏','敏感','安全','身份证','手机号','银行卡','分享','复制','TXT'],
  },
];

export const guideFaqs: GuideFaq[] = [
  {id:'offline',question:'没网络时能做什么？',answer:'可查看应用内置且明确标记的离线样例，以及当前设备的个人资料、已确认课表和本机演示预览。真实导入、账户事项、材料库、知识库及账户日程需要连接后端；浏览器首次载入页面也需要取得应用资源。',topic:'import',keywords:['离线','断网','网络','演示']},
  {id:'connection',question:'提示“无法连接在线服务”怎么办？',answer:'先到登录页点击“检查服务连接”。电脑浏览器需确保后端已启动；手机上的 127.0.0.1 指手机自身，测试包需配置手机可访问的服务地址。确认连接后再重试；已保存批次可从导入页的“继续”入口恢复。',topic:'import',keywords:['连接','后端','登录','服务','手机','127.0.0.1']},
  {id:'partial',question:'网页、图片或部分文件读取失败怎么办？',answer:'在来源列表查看具体失败原因。检查访问权限、格式、体积、页数与图片清晰度，必要时补充正文或重新选择文件。有成功来源时可以部分分析，但应继续核对缺失附件，结果不会覆盖未读取内容。',topic:'import',keywords:['OCR','图片','PDF','失败','网页','部分分析','附件']},
  {id:'unknown',question:'为什么补了资料还是“待确认”？',answer:'检查资料卡是否已确认、是否过期、是否适用当前事项，以及同一字段有无冲突。通知缺少可计算条件、关键附件未齐，或某些原文条件无法计算时，也会保持待确认。请按页面列出的缺失原因继续核对。',topic:'profile',keywords:['UNKNOWN','待确认','画像','资料','冲突','过期']},
  {id:'dates',question:'为什么要自己确认日期和步骤？',answer:'通知中的日期可能是发布日期、活动时间或不同阶段的截止日期，提取出的行动也可能包含可取消的建议。确认前请对照原文选择；信息不明时可以暂不设置日期，系统不会因此保证按时完成。',topic:'analysis',keywords:['确认','日期','步骤','截止','候选']},
  {id:'ai',question:'每次分析都会调用 AI 吗？',answer:'不会。是否调用 AI 取决于后端配置及可用性；未配置或调用失败时会使用可用的本地规则并如实提示。请以页面实际分析方式、原文证据和待核对提示为准，不要仅凭“分析完成”判断信息已经完整。',topic:'analysis',keywords:['AI','模型','本地规则','回退','分析方式']},
  {id:'no-schedule',question:'步骤为什么没有排进日程？',answer:'先确认事项、行动步骤、预计耗时和排程所需信息，再查看“未安排”原因。前置依赖、截止日期、课程和忙碌时段、每日时长上限都会影响安排；调整后重新预览并确认草稿。',topic:'plan',keywords:['未安排','排程','耗时','依赖','日程']},
  {id:'feedback',question:'还有问题，如何提供反馈？',answer:'记录出现问题的页面、操作步骤、预期结果与实际结果。在“帮助与反馈”点击“复制诊断信息”，连同问题描述自行提供给项目支持人员。分享截图前请遮盖个人信息；应用目前不会代你发送反馈。',topic:'privacy',keywords:['反馈','帮助','诊断','错误','截图']},
];

function normalize(value:string){return value.normalize('NFKC').toLocaleLowerCase().trim()}
export function searchGuide(query:string){
  const terms=normalize(query).split(/\s+/).filter(Boolean);
  const matches=(value:string)=>terms.every(term=>normalize(value).includes(term));
  return {
    chapters:guideChapters.filter(chapter=>matches([chapter.title,chapter.summary,chapter.scene,chapter.result,...chapter.notes,...chapter.keywords,...chapter.steps.flatMap(step=>[step.title,step.description])].join(' '))),
    faqs:guideFaqs.filter(faq=>matches([faq.question,faq.answer,...faq.keywords].join(' '))),
  };
}
export function guideTopic(value:unknown):GuideTopic|undefined{
  return typeof value==='string'?guideChapters.find(chapter=>chapter.id===value)?.id:undefined;
}
