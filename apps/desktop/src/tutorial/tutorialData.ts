// Authored, bundled examples. This module and the tutorial never import an API client.
export const TUTORIAL_STORY = {
  title: "末班灯火",
  genre: "温暖 / 亲情 / 雨夜",
  chapterTitle: "第一章 · 灯还亮着",
  novel: `青岚站停运前的最后一晚，雨落得很密。

林晚站在空荡的站台上，蓝灰色雨衣的袖口已经湿透。她手里攥着一张泛黄的车票，日期停在十二年前。父亲留下的纸箱里，只有这张票的背面写着青岚站的地址。

候车室的灯忽然亮了。一个穿深褐色旧外套的男人推开门，手里提着煤油灯。

“你是林远的女儿？”他问。

林晚点头。男人看了看车票，没有再问。他叫陈叔，是这座小站最后的值守人。明天起，这条支线就不再有列车经过。

陈叔从柜台下取出一个旧信封。“你父亲托我转交给你。我答应他，等你亲自来拿。”

林晚拆开信。纸上只有几行字：那年父亲没能赶上回家的车，陈叔在雨里为他留了一盏灯。后来，每逢最后一班车进站，父亲都会来陪陈叔坐一会儿。他没有告诉女儿，是因为他一直觉得，善意不必成为一件需要讲述的事。

“这张票，晚了十二年。”林晚轻声说。

陈叔摇摇头，把煤油灯放到她面前。“灯亮着，就不算晚。”

远处传来最后一班车的汽笛。林晚本来打算拿到信就走，此刻却把车票仔细放回信封，坐在陈叔身旁。

“我替他，陪您等最后一班。”

两人没有再说话。暖黄色的灯照着湿润的站台，雨声慢慢被车轮声盖过去。林晚终于明白，父亲留下的不是一张过期车票，而是一条仍然通向家的路。`,
  bible: {
    synopsis:
      "林晚带着父亲留下的旧车票来到即将停运的小站，得到陈叔守候十二年的信，选择留下陪他等最后一班车。",
    world: "当代青岚小站，停运前的雨夜；冷蓝雨景与暖黄灯火形成对照。",
    theme: "被记住的善意，让告别也有归处。",
    characters: [
      {
        name: "林晚",
        description: "23 岁，短黑发、蓝灰雨衣。起初急着寻求答案，读信后变得温柔坚定。",
        image: "lin-wan.svg",
      },
      {
        name: "陈叔",
        description: "58 岁，灰短发、深褐旧外套。青岚站最后的值守人，寡言但守信。",
        image: "chen-shu.svg",
      },
    ],
    location: {
      name: "青岚站",
      description: "空荡站台、旧候车室、雨夜。木长椅和一盏煤油灯作为稳定空间锚点。",
      image: "station.svg",
    },
    prop: {
      name: "旧车票与信",
      description: "泛黄的十二年前车票夹在旧信封中，是连接父女与陈叔的线索。",
      image: "ticket.svg",
    },
  },
  scene: {
    title: "第 1 集 · 灯还亮着",
    slugline: "外景 · 青岚站台 · 夜 / 雨",
    action:
      "林晚穿过雨幕走上站台。陈叔提灯出现，将旧信递给她。她读完信，选择坐下陪他守候最后一班车。",
    dialogue: [
      "林晚：这张票，晚了十二年。",
      "陈叔：灯亮着，就不算晚。",
      "林晚：我替他，陪您等最后一班。",
    ],
  },
  shots: [
    {
      number: 1,
      type: "全景",
      camera: "缓慢推近",
      action: "林晚走上雨中的空站台，候车室透出灯光。",
      dialogue: "",
      prompt: "雨夜小站，蓝灰雨衣的年轻女子，冷蓝雨景与暖黄灯火，横向电影构图。",
      image: "shot-1.svg",
      clip: "shot-1.mp4",
      references: "林晚、青岚站",
    },
    {
      number: 2,
      type: "中景",
      camera: "固定机位",
      action: "陈叔提灯递信，林晚伸手接过。",
      dialogue: "这张票，晚了十二年。",
      prompt: "同一站台，蓝灰雨衣女子与深褐外套老人相对，旧信封居中，暖灯照亮两人的脸。",
      image: "shot-2.svg",
      clip: "shot-2.mp4",
      references: "林晚、陈叔、青岚站、旧车票与信",
    },
    {
      number: 3,
      type: "特写",
      camera: "轻微推近",
      action: "车票与信停在暖光里，林晚的手不再颤抖。",
      dialogue: "灯亮着，就不算晚。",
      prompt: "手中泛黄车票与旧信封特写，煤油灯暖光，背景雨幕虚化，保留纸张纹理。",
      image: "shot-3.svg",
      clip: "shot-3.mp4",
      references: "旧车票与信",
    },
    {
      number: 4,
      type: "双人全景",
      camera: "缓慢拉远",
      action: "林晚与陈叔并肩坐下，远处列车灯光靠近。",
      dialogue: "我替他，陪您等最后一班。",
      prompt:
        "同一雨夜站台，两人并肩坐在木长椅上，蓝灰雨衣与深褐外套，暖灯和远处列车灯光。",
      image: "shot-4.svg",
      clip: "shot-4.mp4",
      references: "林晚、陈叔、青岚站",
    },
  ],
} as const;

export const TUTORIAL_MODULES = [
  { id: "project", label: "主页" },
  { id: "novel", label: "小说" },
  { id: "bible", label: "故事圣经" },
  { id: "script", label: "剧本" },
  { id: "assets", label: "资产" },
  { id: "storyboard", label: "分镜" },
  { id: "generation", label: "生成中心" },
] as const;
export type TutorialModule = (typeof TUTORIAL_MODULES)[number]["id"];

interface TutorialStep {
  module: TutorialModule;
  target: string;
  title: string;
  instruction: string;
  realUse: string;
  continueLabel?: string;
}

export const TUTORIAL_STEPS: readonly TutorialStep[] = [
  {
    module: "project",
    target: "start",
    title: "先拍一部免费示例剧",
    instruction:
      "用《末班灯火》练习完整制作流程。点亮的区域就是下一步，素材已经备好，无需配置模型。",
    realUse: "教程中的生成按钮只载入内置模板，退出后再制作自己的项目。",
  },
  {
    module: "project",
    target: "create-project",
    title: "给故事一个工作空间",
    instruction: "点击「创建示例项目」。小说、设定、剧本和生成结果都应归属于同一个项目。",
    realUse: "实际创作：在主页新建项目，再进入各个模块。",
  },
  {
    module: "project",
    target: "nav-novel",
    title: "从小说开始",
    instruction: "项目已就绪。点击顶部高亮的「小说」，准备故事原文。",
    realUse: "可以导入已有小说，也可以用文本模型创作。",
  },
  {
    module: "novel",
    target: "import-novel",
    title: "导入故事原文",
    instruction: "点击「导入示例小说」，载入预先写好的第一章。",
    realUse: "小说模块支持 TXT / MD / DOCX；AI 写作会使用你配置的文本模型。",
  },
  {
    module: "novel",
    target: "novel-content",
    title: "先检查故事",
    instruction:
      "看看人物、地点和事件是否清楚。林晚、陈叔、青岚站和旧车票将成为后续制作的依据。",
    realUse: "先修改小说再分析，后续结果才会沿用正确设定。",
    continueLabel: "阅读完毕，继续",
  },
  {
    module: "novel",
    target: "nav-bible",
    title: "建立故事圣经",
    instruction: "点击「故事圣经」，把小说整理成大家共同遵守的设定。",
    realUse: "Story Bible 是人物、地点、道具和剧情的一致性依据。",
  },
  {
    module: "bible",
    target: "analyze-story",
    title: "从故事提取设定",
    instruction: "点击「分析故事（示例）」。教程直接展示内置分析结果。",
    realUse: "实际分析需要文本模型；先确认选择了正确的小说。",
  },
  {
    module: "bible",
    target: "bible-content",
    title: "核对人物与世界",
    instruction:
      "检查林晚的蓝灰雨衣、陈叔的深褐外套以及雨夜站台。稳定的描述有助于后续画面一致。",
    realUse: "发现提取错误时先修正 Story Bible，再生成剧本和参考资产。",
    continueLabel: "设定已核对",
  },
  {
    module: "bible",
    target: "nav-script",
    title: "把文字变成戏",
    instruction: "点击「剧本」，把小说改编成可以拍摄的场景与对白。",
    realUse: "剧本按分集组织，再分成场景。",
  },
  {
    module: "script",
    target: "generate-script",
    title: "生成分集剧本",
    instruction: "点击「生成剧本（示例）」，查看动作、地点和角色对白。",
    realUse: "实际生成时选择小说与文本模型；生成后先预览，不直接当作最终稿。",
  },
  {
    module: "script",
    target: "save-script",
    title: "审核后再保存",
    instruction:
      "检查右侧预览，然后点击「保存剧本（示例）」。生成与保存是两步，你可以先修改不满意的内容。",
    realUse: "保存后的场景才会成为分镜制作的输入。",
  },
  {
    module: "script",
    target: "nav-assets",
    title: "准备可复用的资产",
    instruction: "点击「资产」，为人物、地点和道具建立参考。",
    realUse: "复用参考图可以减少不同镜头之间的外观漂移。",
  },
  {
    module: "assets",
    target: "generate-assets",
    title: "建立参考图",
    instruction:
      "点击「生成参考图（示例）」，一次载入两个人物、一个地点和一个道具的本地插画。",
    realUse: "实际使用可导入已有参考图，也可以选择图片模型生成；结果保留版本。",
  },
  {
    module: "assets",
    target: "asset-content",
    title: "检查参考资产",
    instruction:
      "确认服装、地点和道具符合设定。后续镜头将引用这些资产，而不是每次重新描述人物。",
    realUse: "角色图通常使用三视图；这里用示意插画讲解参考关系。",
    continueLabel: "参考资产已核对",
  },
  {
    module: "assets",
    target: "nav-storyboard",
    title: "进入分镜制作",
    instruction: "点击「分镜」，把场景拆成镜头。",
    realUse: "真实分镜由剧本场景生成，可在剧本模块生成后进入此处编辑。",
  },
  {
    module: "storyboard",
    target: "generate-shots",
    title: "为场景规划镜头",
    instruction:
      "点击「生成分镜（示例）」，载入四个镜头，每个五秒。景别、运镜、动作和台词共同说明怎么拍。",
    realUse: "真实创作：在剧本的场景卡片上生成并保存分镜，然后到分镜模块调整。",
  },
  {
    module: "storyboard",
    target: "generate-images",
    title: "先做关键帧",
    instruction:
      "点击「生成分镜图（示例）」。每个镜头会引用对应人物、地点和道具，载入一张关键帧。",
    realUse: "检查关键帧后再生成视频；图片不满意时只重做当前镜头。",
  },
  {
    module: "storyboard",
    target: "generate-videos",
    title: "从关键帧到视频",
    instruction:
      "点击「生成视频（示例）」，载入四条已经制作好的短视频。可以播放第一条看看效果。",
    realUse:
      "图生视频用关键帧固定主体，再用提示词补充动作。教程短片无声，真实音频支持取决于模型。",
  },
  {
    module: "storyboard",
    target: "nav-generation",
    title: "汇总本集制作状态",
    instruction: "点击「生成中心」，检查整集是否已经具备交付条件。",
    realUse: "制作台汇总缺失项、失败任务和参考版本问题，可跳回对应镜头处理。",
  },
  {
    module: "generation",
    target: "prepare-episode",
    title: "先预检，再合成",
    instruction: "点击「准备本集（示例）」，核对四个镜头的剧本、参考图、关键帧和视频。",
    realUse: "真实「准备本集」是免费预检，不创建付费任务；实际批量生成要检查模型与参数。",
  },
  {
    module: "generation",
    target: "compose-episode",
    title: "合成本集",
    instruction:
      "本集素材完整。点击「合成本集（示例）」，打开已离线制作好的 20 秒示例短片。",
    realUse: "真实创作可合成场景或分集视频；不满意时回到对应镜头局部重做。",
  },
  {
    module: "generation",
    target: "finished-film",
    title: "你的第一遍制作流程已完成",
    instruction:
      "播放《末班灯火》，回顾小说 → 设定 → 剧本 → 参考资产 → 分镜 → 图片 → 视频 → 合成。你可以结束教程，或从头再练一次。",
    realUse:
      "开始自己的剧：新建项目、配置模型、导入小说并按这条流程制作。保存与预览免费；实际 AI 生成按服务商计费。",
    continueLabel: "完成教程",
  },
];

export function advanceTutorial(index: number, target: string): number {
  if (TUTORIAL_STEPS[index]?.target !== target) return index;
  return Math.min(index + 1, TUTORIAL_STEPS.length - 1);
}

export const tutorialMedia = (filename: string) => `/tutorial/${filename}`;
