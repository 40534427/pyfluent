/* Lingua · 中央 Mock 数据源（所有页面只从这里取数） */
(function () {
  const LANGS = [
    { id: 'en', name: '英语', native: 'English', badge: 'EN', speech: 'en-US', tone: 'green',
      tagline: '把世界，说给你听', blurb: '从 A1 到 B2 的完整分级路径，覆盖旅行、职场与深度表达。',
      learners: 128400, greeting: 'Hello', sample: 'Serendipity' },
    { id: 'ja', name: '日语', native: '日本語', badge: 'JA', speech: 'ja-JP', tone: 'red',
      tagline: '从五十音，走进日常', blurb: 'N5 到 N3 的阶梯课程，敬语、会话与新闻听力一次练透。',
      learners: 86200, greeting: 'こんにちは', sample: '木漏れ日' },
    { id: 'ko', name: '韩语', native: '한국어', badge: 'KO', speech: 'ko-KR', tone: 'amber',
      tagline: '读懂字里行间的温度', blurb: 'TOPIK 1–3 分级训练，追剧口语与职场表达双线并行。',
      learners: 61400, greeting: '안녕하세요', sample: '설레다' }
  ];

  const BLUEPRINT = {
    en: {
      levels: [
        { id: 'en-a1', code: 'A1', title: '入门筑基', desc: '日常问候、购物与出行，建立开口的底气', units: [
          { title: '初次见面', scene: '街角咖啡馆 · 第一次打招呼', lessons: ['Greetings · 打招呼', 'Introduce Yourself · 自我介绍', 'Small Talk · 闲聊开场'] },
          { title: '日常生活', scene: '公寓与超市 · 一天的生活', lessons: ['Daily Routine · 一天的生活', 'Food & Drink · 饮食偏好', 'Shopping · 购物问价'] }
        ] },
        { id: 'en-a2', code: 'A2', title: '生活进阶', desc: '旅行、点餐与表达感受，应对真实场景', units: [
          { title: '城市漫游', scene: '地铁站与酒店 · 出行全流程', lessons: ['Asking for Directions · 问路', 'Taking the Subway · 搭乘地铁', 'At the Hotel · 酒店入住'] },
          { title: '味觉地图', scene: '咖啡馆与餐厅 · 点单与评价', lessons: ['Ordering Coffee · 点一杯咖啡', 'At a Restaurant · 餐厅用餐', 'Talking About Taste · 描述味道'] }
        ] },
        { id: 'en-b1', code: 'B1', title: '流利表达', desc: '观点、故事与职场沟通，说出完整想法', units: [
          { title: '观点交锋', scene: '读书会 · 表达与回应', lessons: ['Giving Opinions · 表达观点', 'Agreeing & Disagreeing · 赞同与反驳', 'Storytelling · 讲一个故事'] },
          { title: '职场起步', scene: '办公室 · 会议与邮件', lessons: ['Job Interview · 面试问答', 'Emails That Work · 写一封邮件', 'Meeting Talk · 会议发言'] }
        ] },
        { id: 'en-b2', code: 'B2', title: '深度思辨', desc: '抽象话题、演讲与跨文化表达', units: [
          { title: '思想表达', scene: '公开演讲 · 结构与分寸', lessons: ['Nuance & Tone · 语气与分寸', 'Debate Skills · 辩论技巧', 'Presenting Ideas · 演讲结构'] },
          { title: '文化视野', scene: '跨文化对谈 · 理解差异', lessons: ['Culture Shock · 文化冲击', 'Media Literacy · 信息素养', 'Travel Essays · 旅行写作'] }
        ] }
      ]
    },
    ja: {
      levels: [
        { id: 'ja-n5', code: 'N5', title: '入门五十音', desc: '假名、问候与自我介绍，打好发音地基', units: [
          { title: 'はじめまして', scene: '教室 · 第一次见面', lessons: ['あいさつ · 问候', '自己紹介 · 自我介绍', 'ひらがな · 平假名'] },
          { title: '毎日のこと', scene: '家与便利店 · 日常片段', lessons: ['毎日の予定 · 每日安排', '好きなもの · 喜欢的事物', '買い物 · 购物'] }
        ] },
        { id: 'ja-n4', code: 'N4', title: '生活表达', desc: '日常会话与基础阅读，敢说也敢问', units: [
          { title: '街を歩く', scene: '街道与电车 · 城市移动', lessons: ['道を聞く · 问路', '電車に乗る · 搭乘电车', 'カフェで · 在咖啡馆'] },
          { title: '気持ちを伝える', scene: '朋友聚会 · 表达心情', lessons: ['お願いする · 提出请求', '感想を言う · 表达感受', '誘う・断る · 邀请与拒绝'] }
        ] },
        { id: 'ja-n3', code: 'N3', title: '自然表达', desc: '敬语、观点与新闻听力，接近母语节奏', units: [
          { title: '敬語の扉', scene: '职场 · 上下级沟通', lessons: ['尊敬語 · 尊敬语', '謙譲語 · 谦让语', 'ビジネスメール · 商务邮件'] },
          { title: '考えを話す', scene: '讨论会 · 有条理地表达', lessons: ['意見を述べる · 陈述观点', 'ニュースを聞く · 听新闻', '作文の組み立て · 写作结构'] }
        ] }
      ]
    },
    ko: {
      levels: [
        { id: 'ko-t1', code: 'TOPIK 1', title: '入门发音', desc: '韩文字母、问候与自我介绍，先读准再开口', units: [
          { title: '첫 만남', scene: '校园 · 初次见面', lessons: ['인사 · 问候', '자기소개 · 自我介绍', '한글 모음 · 韩文元音'] },
          { title: '일상생활', scene: '宿舍与便利店 · 一天', lessons: ['하루 일과 · 一天作息', '좋아하는 것 · 喜欢的事物', '쇼핑하기 · 购物'] }
        ] },
        { id: 'ko-t2', code: 'TOPIK 2', title: '日常会话', desc: '点餐、出行与情感表达，生活场景全覆盖', units: [
          { title: '서울 산책', scene: '地铁与咖啡街 · 城市漫游', lessons: ['길 묻기 · 问路', '지하철 타기 · 搭乘地铁', '카페에서 · 在咖啡馆'] },
          { title: '마음 표현', scene: '朋友聚会 · 说出感受', lessons: ['부탁하기 · 提出请求', '감정 말하기 · 表达情感', '약속 잡기 · 约定时间'] }
        ] },
        { id: 'ko-t3', code: 'TOPIK 3', title: '流畅沟通', desc: '职场、观点与媒体，进入自然交流层', units: [
          { title: '직장 생활', scene: '公司 · 面试与会议', lessons: ['면접 보기 · 面试', '이메일 쓰기 · 写邮件', '회의 말하기 · 会议发言'] },
          { title: '생각 나누기', scene: '讨论节目 · 观点与新闻', lessons: ['의견 말하기 · 表达观点', '뉴스 듣기 · 听新闻', '글쓰기 · 写作练习'] }
        ] }
      ]
    }
  };

  const courses = {};
  LANGS.forEach(function (lang) {
    const bp = BLUEPRINT[lang.id];
    const levels = bp.levels.map(function (level, li) {
      return {
        id: level.id, code: level.code, title: level.title, desc: level.desc, index: li,
        units: level.units.map(function (unit, ui) {
          return {
            id: level.id + '-u' + (ui + 1), title: unit.title, scene: unit.scene,
            lessons: unit.lessons.map(function (title, idx) {
              return {
                id: level.id + '-u' + (ui + 1) + '-l' + (idx + 1),
                title: title,
                lang: lang.id,
                levelCode: level.code,
                levelId: level.id,
                unitId: level.id + '-u' + (ui + 1),
                unitTitle: unit.title,
                minutes: 7 + ((ui + idx) % 4) * 2,
                xp: 30 + ui * 10 + idx * 5,
                tags: [['词汇', '会话'], ['语法', '表达'], ['听力', '口语']][idx % 3]
              };
            })
          };
        })
      };
    });
    courses[lang.id] = {
      lang: lang.id,
      title: lang.name,
      native: lang.native,
      levels: levels,
      totalLessons: levels.reduce(function (sum, l) {
        return sum + l.units.reduce(function (s, u) { return s + u.lessons.length; }, 0);
      }, 0)
    };
  });

  const decks = {
    en: {
      words: [
        { term: 'serendipity', ipa: '/ˌserənˈdɪpəti/', meaning: '意外发现美好事物的运气', example: 'Finding this tiny café was pure serendipity.', exampleCn: '发现这家小咖啡馆，纯属意外之喜。' },
        { term: 'resilient', ipa: '/rɪˈzɪliənt/', meaning: '有韧性的；能迅速恢复的', example: 'She stayed resilient after the setback.', exampleCn: '遭遇挫折后，她依然保持着韧性。' },
        { term: 'wanderlust', ipa: '/ˈwɒndəlʌst/', meaning: '对旅行的强烈渴望', example: 'His wanderlust took him all the way to Kyoto.', exampleCn: '对远方的渴望把他一路带到了京都。' },
        { term: 'nuance', ipa: '/ˈnjuːɑːns/', meaning: '细微差别；语气分寸', example: 'Japanese has a different nuance for every mood.', exampleCn: '日语里每一种情绪都有不同的语感。' },
        { term: 'itinerary', ipa: '/aɪˈtɪnərəri/', meaning: '行程单；旅行计划', example: 'Our itinerary covers three cities in five days.', exampleCn: '我们的行程五天内覆盖三座城市。' },
        { term: 'collaborate', ipa: '/kəˈlæbəreɪt/', meaning: '协作；共同完成', example: 'We collaborate across three time zones.', exampleCn: '我们跨越三个时区协作。' },
        { term: 'daunting', ipa: '/ˈdɔːntɪŋ/', meaning: '令人望而生畏的', example: 'Speaking in public felt daunting at first.', exampleCn: '一开始，当众讲话让人望而生畏。' },
        { term: 'breeze', ipa: '/briːz/', meaning: '轻而易举的事；微风', example: 'After practice, the interview was a breeze.', exampleCn: '练习之后，面试变得轻而易举。' }
      ],
      grammar: [
        { q: 'She ___ to the gym every morning.', options: ['go', 'goes', 'going', 'gone'], answer: 1, explain: '一般现在时中，第三人称单数作主语时动词加 -s，故用 goes。' },
        { q: 'If I ___ more time, I would travel around Japan.', options: ['have', 'had', 'will have', 'having'], answer: 1, explain: '与现在事实相反的虚拟语气：从句用过去式 had，主句用 would + 动词原形。' },
        { q: 'The book ___ by a young author last year.', options: ['wrote', 'was written', 'has written', 'is writing'], answer: 1, explain: '书是“被写”的，且时间状语为 last year，用一般过去时的被动语态 was written。' },
        { q: 'I look forward to ___ from you.', options: ['hear', 'hearing', 'heard', 'be heard'], answer: 1, explain: 'look forward to 中 to 是介词，后接动名词，故用 hearing。' }
      ],
      speaking: [
        { sentence: 'Could you recommend a good coffee shop nearby?', translation: '你能推荐附近一家不错的咖啡馆吗？', tip: '注意 Could you 之间轻度连读，句尾用升调显得更礼貌。' },
        { sentence: "I'd like to book a table for two at seven.", translation: '我想订一张七点的两人桌。', tip: 'I’d like to 常弱读为 /aɪd laɪk tə/，数字 seven 要清晰。' },
        { sentence: 'Honestly, I never expected to fall in love with this city.', translation: '说实话，我从没想过会爱上这座城市。', tip: 'Honestly 后稍作停顿，fall in love 连读为 /fɔːlɪn lʌv/。' }
      ],
      listening: [
        { text: 'Excuse me, does this train go to the city center?', translation: '打扰一下，这趟列车是开往市中心的吗？', question: '说话者在询问什么？', options: ['列车时刻', '列车是否开往市中心', '车票价格', '如何换乘'], answer: 1, transcript: 'Excuse me, does this train go to the city center?' },
        { text: 'The museum is closed on Mondays, but it stays open until nine on Fridays.', translation: '博物馆周一闭馆，但周五开放到晚上九点。', question: '周五博物馆几点关门？', options: ['下午五点', '晚上七点', '晚上九点', '周一不开放'], answer: 2, transcript: 'The museum is closed on Mondays, but it stays open until nine on Fridays.' }
      ]
    },
    ja: {
      words: [
        { term: '木漏れ日', ipa: 'こもれび', meaning: '树叶间洒落的阳光', example: '木漏れ日がとてもきれいです。', exampleCn: '叶隙间的阳光非常美。' },
        { term: '頑張る', ipa: 'がんばる', meaning: '努力；加油', example: '毎日日本語を頑張っています。', exampleCn: '我每天都在努力学日语。' },
        { term: 'お疲れ様', ipa: 'おつかれさま', meaning: '辛苦了（寒暄语）', example: 'お疲れ様です、また明日。', exampleCn: '辛苦了，明天见。' },
        { term: '空気を読む', ipa: 'くうきをよむ', meaning: '察言观色；读懂气氛', example: '彼は空気を読むのが上手です。', exampleCn: '他很擅长察言观色。' },
        { term: 'もったいない', ipa: 'もったいない', meaning: '可惜的；浪费的', example: '捨てるのはもったいないです。', exampleCn: '丢掉太可惜了。' },
        { term: '居心地', ipa: 'いごこち', meaning: '待着的舒适感', example: 'このカフェは居心地がいい。', exampleCn: '这家咖啡馆待着很舒服。' },
        { term: '初詣', ipa: 'はつもうで', meaning: '新年初次参拜', example: 'お正月に初詣に行きます。', exampleCn: '正月要去新年初次参拜。' },
        { term: '段取り', ipa: 'だんどり', meaning: '安排；步骤', example: '段取りを確認しましょう。', exampleCn: '我们确认一下流程安排吧。' }
      ],
      grammar: [
        { q: '私は毎朝、コーヒー___飲みます。', options: ['が', 'を', 'に', 'で'], answer: 1, explain: '「飲む」是他动词，宾语用助词「を」标记：コーヒーを飲みます。' },
        { q: '明日、雨___降るでしょう。', options: ['が', 'を', 'は', 'も'], answer: 0, explain: '自然现象的主体用「が」：雨が降る。' },
        { q: 'この本は弟___書かれました。', options: ['に', 'で', 'によって', 'から'], answer: 2, explain: '被动句中表示动作执行者，书面语常用「によって」。' },
        { q: '日本語を勉強___います。', options: ['して', 'する', 'した', 'します'], answer: 0, explain: '「〜ている」表示正在进行的动作：勉強しています。' }
      ],
      speaking: [
        { sentence: 'すみません、駅までの道を教えていただけますか。', translation: '不好意思，能告诉我到车站的路吗？', tip: '「教えていただけますか」是礼貌请求，语速放慢更自然。' },
        { sentence: 'この料理はとても美味しいですね。', translation: '这道菜非常好吃呢。', tip: '「美味しい」重音在「い」前，句尾「ですね」轻微上扬。' },
        { sentence: '週末は一緒に映画を見に行きませんか。', translation: '周末要不要一起去看电影？', tip: '「行きませんか」是邀请表达，注意「見に行く」的连读。' }
      ],
      listening: [
        { text: 'すみません、この電車は渋谷に行きますか。', translation: '不好意思，这趟电车去涩谷吗？', question: '说话者在确认什么？', options: ['电车的时间', '电车是否去涩谷', '车票多少钱', '在哪里换乘'], answer: 1, transcript: 'すみません、この電車は渋谷に行きますか。' },
        { text: '週末は友達と映画を見に行こうと思っています。', translation: '周末打算和朋友去看电影。', question: '说话者周末打算做什么？', options: ['在家休息', '和朋友看电影', '去公司加班', '一个人旅行'], answer: 1, transcript: '週末は友達と映画を見に行こうと思っています。' }
      ]
    },
    ko: {
      words: [
        { term: '눈치', ipa: 'nun-chi', meaning: '察言观色；眼力见', example: '그는 눈치가 빨라요.', exampleCn: '他很有眼力见。' },
        { term: '정', ipa: 'jeong', meaning: '情分；人与人的眷恋', example: '한국 사람들의 정을 느꼈어요.', exampleCn: '我感受到了韩国人的情分。' },
        { term: '설레다', ipa: 'seol-le-da', meaning: '心动；心里发烫', example: '여행을 앞두고 마음이 설레요.', exampleCn: '临近旅行，心里很激动。' },
        { term: '맛집', ipa: 'mat-jip', meaning: '美食店；好吃的店', example: '이 근처 맛집을 알려 주세요.', exampleCn: '请告诉我附近好吃的店。' },
        { term: '꿀팁', ipa: 'kkul-tip', meaning: '实用小技巧', example: '여행 꿀팁을 공유할게요.', exampleCn: '我来分享旅行小技巧。' },
        { term: '어색하다', ipa: 'eo-saek-ha-da', meaning: '尴尬的；不自然的', example: '처음에는 조금 어색했어요.', exampleCn: '一开始有点尴尬。' },
        { term: '힐링', ipa: 'hil-ling', meaning: '治愈；放松', example: '주말에는 힐링이 필요해요.', exampleCn: '周末需要治愈一下。' },
        { term: '눈물이 나다', ipa: 'nun-mul-i na-da', meaning: '流泪', example: '그 영화를 보고 눈물이 났어요.', exampleCn: '看了那部电影就哭了。' }
      ],
      grammar: [
        { q: '저는 매일 커피___ 마셔요.', options: ['를', '가', '에', '도'], answer: 0, explain: '「마시다」是他动词，宾语用宾格助词「를」：커피를 마셔요。' },
        { q: '내일 비___ 올 거예요.', options: ['를', '가', '에서', '보다'], answer: 1, explain: '自然现象的主体用主格助词「가」：비가 오다。' },
        { q: '이 책은 동생___ 쓴 거예요.', options: ['이', '에', '를', '와'], answer: 0, explain: '「동생이 쓰다」中动作主体用「이」，故为 동생이 쓴 거예요。' },
        { q: '한국어를 배우___ 있어요.', options: ['고', '서', '면', '지만'], answer: 0, explain: '「배우고 있어요」表示正在学习，用「-고 있다」进行时。' }
      ],
      speaking: [
        { sentence: '이 근처에 조용한 카페가 있을까요?', translation: '这附近有安静的咖啡馆吗？', tip: '「있을까요」句尾轻升，语气更委婉；注意「조용한」的连读。' },
        { sentence: '오늘 정말 즐거웠어요. 다음에 또 만나요.', translation: '今天真的很开心，下次再见。', tip: '「즐거웠어요」重音在「거」，收尾放松自然。' },
        { sentence: '주말에 같이 등산할래요?', translation: '周末要一起去爬山吗？', tip: '「할래요」是口语邀请，语调上扬，显得亲切。' }
      ],
      listening: [
        { text: '저기요, 이 버스 시청에 가요?', translation: '打扰一下，这趟公交去市政府吗？', question: '说话者在询问什么？', options: ['公交的票价', '公交是否去市政府', '下一站是哪里', '怎么换乘'], answer: 1, transcript: '저기요, 이 버스 시청에 가요?' },
        { text: '주말에 같이 등산할래요? 날씨가 좋대요.', translation: '周末要一起爬山吗？听说天气很好。', question: '为什么想周末去爬山？', options: ['因为门票便宜', '因为天气很好', '因为朋友很多', '因为想减肥'], answer: 1, transcript: '주말에 같이 등산할래요? 날씨가 좋대요.' }
      ]
    }
  };

  const posts = [
    { id: 'p1', author: '苏黎', lang: 'ja', badge: 'JA', time: '12 分钟前', tag: '#日语学习',
      content: '今天终于把「木漏れ日」用进了作文里。老师批注说“很有画面感”，那一刻觉得背单词的枯燥都值了。',
      lesson: 'N4 · 気持ちを伝える', likes: 42, liked: false,
      comments: [
        { author: '夏树', text: '这个词太美了，我也要加进生词本。', time: '8 分钟前' },
        { author: '阿岚', text: '恭喜！被老师夸真的会开心一整天。', time: '5 分钟前' }
      ] },
    { id: 'p2', author: 'Kenji', lang: 'en', badge: 'EN', time: '35 分钟前', tag: '#方法分享',
      content: '分享一个练听力的笨办法：同一段播客听三遍。第一遍抓关键词，第二遍看字幕，第三遍不看字幕复述。两周后耳朵真的会变。',
      lesson: 'B1 · Meeting Talk', likes: 87, liked: false,
      comments: [
        { author: 'Theo', text: '第三遍复述这步太关键了，之前一直跳过。', time: '20 分钟前' }
      ] },
    { id: 'p3', author: '小满', lang: 'ko', badge: 'KO', time: '1 小时前', tag: '#找搭子',
      content: '求一位韩语口语搭子！目前 TOPIK 2 水平，每天想练 15 分钟，可以互相纠音。',
      lesson: 'TOPIK 2 · 카페에서', likes: 23, liked: false,
      comments: [
        { author: 'Minji', text: '我可以，晚上八点后都有空。', time: '40 分钟前' },
        { author: '小满', text: '太好了，已私信你～', time: '36 分钟前' }
      ] },
    { id: 'p4', author: 'Aria', lang: 'en', badge: 'EN', time: '2 小时前', tag: '#打卡',
      content: '连续打卡第 100 天。回头看第一天的录音，发音抖得厉害；今天再录同一句，居然有点从容了。',
      lesson: 'A2 · Talking About Taste', likes: 156, liked: false, comments: [
        { author: '林知夏', text: '100 天！这就是坚持的样子。', time: '1 小时前' }
      ] },
    { id: 'p5', author: '阿岚', lang: 'ja', badge: 'JA', time: '3 小时前', tag: '#求助',
      content: '五十音背了三天还是记不住，尤其是「ぬ」和「め」。大家有什么联想记忆法吗？',
      lesson: 'N5 · ひらがな', likes: 18, liked: false,
      comments: [
        { author: '苏黎', text: '「ぬ」像一根打结的绳子，「め」像眼睛，可以先记形状再记音。', time: '2 小时前' },
        { author: '夏树', text: '每天写十遍，配合发音一起记，一周就顺了。', time: '2 小时前' }
      ] },
    { id: 'p6', author: 'Minji', lang: 'ko', badge: 'KO', time: '5 小时前', tag: '#笔记',
      content: '整理了 20 个追剧常用韩语表达：헐、진짜、대박、눈치…… 有没有人想看第二部分？',
      lesson: 'TOPIK 3 · 뉴스 듣기', likes: 64, liked: false, comments: [] },
    { id: 'p7', author: 'Theo', lang: 'en', badge: 'EN', time: '昨天', tag: '#职场英语',
      content: '第一次全程用英语开完项目会，虽然中间卡了两次，但同事说完全听得懂。原来开口比完美重要。',
      lesson: 'B1 · Meeting Talk', likes: 73, liked: false, comments: [
        { author: 'Kenji', text: '“开口比完美重要”这句话我要记下来。', time: '昨天' }
      ] },
    { id: 'p8', author: '夏树', lang: 'ja', badge: 'JA', time: '昨天', tag: '#听力',
      content: '把每天通勤的 20 分钟用来听 NHK 简讯，一个月后做 N3 听力居然只错了两题。碎片时间真的有用。',
      lesson: 'N3 · ニュースを聞く', likes: 91, liked: false, comments: [] }
  ];

  const leaderboard = [
    { rank: 1, name: 'Aria', xp: 1840, lang: 'en' },
    { rank: 2, name: 'Kenji', xp: 1625, lang: 'en' },
    { rank: 3, name: '苏黎', xp: 1470, lang: 'ja' },
    { rank: 4, name: '林知夏', xp: 1120, lang: 'en', me: true },
    { rank: 5, name: 'Minji', xp: 980, lang: 'ko' },
    { rank: 6, name: '夏树', xp: 860, lang: 'ja' },
    { rank: 7, name: 'Theo', xp: 740, lang: 'en' }
  ];

  const achievements = [
    { id: 'first', name: '初次启程', desc: '完成 1 节课程', icon: 'graduation-cap', goal: 1, current: function (s) { return s.completedLessons.length; } },
    { id: 'streak7', name: '七日之火', desc: '连续打卡 7 天', icon: 'flame', goal: 7, current: function (s) { return s.streak; } },
    { id: 'words100', name: '百词斩', desc: '掌握 100 个单词', icon: 'layers', goal: 100, current: function (s) { return s.wordsMastered.en + s.wordsMastered.ja + s.wordsMastered.ko; } },
    { id: 'speaking80', name: '妙语连珠', desc: '口语跟读达到 80 分', icon: 'mic', goal: 80, current: function (s) { return s.bestSpeaking; } },
    { id: 'grammar', name: '语法全对', desc: '一次语法练习全部答对', icon: 'check-circle', goal: 1, current: function (s) { return s.perfectGrammar ? 1 : 0; } },
    { id: 'social', name: '社群之星', desc: '在社区发布 1 条动态', icon: 'message-circle', goal: 1, current: function (s) { return s.posts.length; } },
    { id: 'nightowl', name: '夜猫子', desc: '在 22:00 后仍坚持学习', icon: 'star', goal: 1, current: function (s) { return s.nightOwl ? 1 : 0; } },
    { id: 'trilingual', name: '三语通', desc: '三种语言都留下学习记录', icon: 'languages', goal: 3, current: function (s) { return ['en', 'ja', 'ko'].filter(function (k) { return s.wordsMastered[k] > 0; }).length; } },
    { id: 'xp3000', name: '三千功名', desc: '累计获得 3000 XP', icon: 'zap', goal: 3000, current: function (s) { return s.xp; } },
    { id: 'lessons10', name: '十全十美', desc: '完成 10 节课程', icon: 'book-open', goal: 10, current: function (s) { return s.completedLessons.length; } }
  ];

  const topics = [
    { tag: '#日语学习', count: 1284 }, { tag: '#方法分享', count: 968 },
    { tag: '#打卡', count: 742 }, { tag: '#职场英语', count: 615 },
    { tag: '#韩语口语', count: 508 }, { tag: '#找搭子', count: 431 }
  ];

  const challenges = [
    { id: 'focus', name: '专注学习 20 分钟', reward: 30, goal: 20, icon: 'clock',
      current: function (s) { return s.minutesToday; }, unit: '分钟' },
    { id: 'speak', name: '完成 1 次口语跟读', reward: 20, goal: 1, icon: 'mic',
      current: function (s) { return s.dailyActions.speaking; }, unit: '次' },
    { id: 'words', name: '复习 10 个单词', reward: 20, goal: 10, icon: 'layers',
      current: function (s) { return s.dailyActions.words; }, unit: '个' }
  ];

  function lessonList(lang) {
    const list = [];
    courses[lang].levels.forEach(function (level) {
      level.units.forEach(function (unit) {
        unit.lessons.forEach(function (lesson) { list.push(lesson); });
      });
    });
    return list;
  }

  function findLesson(lang, id) {
    return lessonList(lang).filter(function (l) { return l.id === id; })[0] || null;
  }

  function langMeta(id) {
    return LANGS.filter(function (l) { return l.id === id; })[0] || LANGS[0];
  }

  window.DB = {
    langs: LANGS,
    courses: courses,
    decks: decks,
    posts: posts,
    leaderboard: leaderboard,
    achievements: achievements,
    topics: topics,
    challenges: challenges,
    modes: [
      { key: 'word', name: '单词记忆', icon: 'layers' },
      { key: 'grammar', name: '语法练习', icon: 'check-circle' },
      { key: 'speaking', name: '口语跟读', icon: 'mic' },
      { key: 'listening', name: '听力训练', icon: 'headphones' }
    ],
    lessonList: lessonList,
    findLesson: findLesson,
    langMeta: langMeta
  };
})();
