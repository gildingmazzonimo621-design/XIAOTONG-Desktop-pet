# 蓝色小嗵 — Desktop Pet

一只来自森林和山野间的小精灵桌面宠物，支持 AI 对话、知识管理和趣味互动。

## 功能

- **AI 对话** — 接入 OpenAI 兼容接口（DeepSeek / GPT / Claude 中转等），和你的桌宠聊天
- **知识管理** — 记忆库支持对话提取、网页爬取、手动添加，按文件夹分类管理
- **角色设定** — 内置默认人设文档，支持自定义修改和追加
- **互动系统** — 喂食、摸头、羽毛球、变猫猫、学习、睡觉/唤醒
- **游戏系统** — 每日签到、任务、成就、商店、背包
- **眼睛追踪** — idle 状态下桌宠的眼睛跟随鼠标
- **物理引擎** — 可拖拽、抛出，带重力回弹
- **网页爬取** — 抓取网页内容整理为知识库条目

## 环境要求

- Windows 10 / 11
- Python 3.10+
- PyQt5

## 安装与运行

```bash
pip install PyQt5
python main.py
```

## 首次使用

1. 启动后右键桌宠 → 📊 查看状态
2. 面板自动跳转到「设置」页
3. 填写你的 API 地址和 Key
4. 点击「测试连接」确认配置成功
5. 切换到「聊天」页开始和桌宠说话

## 数据说明

所有用户数据存储在本机系统目录，**不会**保存在项目文件夹中：

```
%APPDATA%\DesktopPet\
├── chat_config.json    # API 配置
├── chat_memory.json    # 聊天记录与记忆
├── pet_save.json       # 宠物状态存档
├── game_data.json      # 游戏进度
└── avatar_custom.png   # 自定义头像
```

## 角色设定

项目内置默认角色设定文档 `data/default_persona.txt`，首次启动时自动加载。

你可以：
- 直接编辑 `data/default_persona.txt` 修改基础人设
- 在「记忆管理」中添加额外的角色设定文档（.txt）
- 通过对话让桌宠记住新设定

## 项目结构

```
desktop-pet/
├── main.py                     # 入口（桌宠窗口、物理引擎、托盘菜单）
├── data/
│   └── default_persona.txt     # 内置角色设定
├── src/
│   ├── user_data.py            # 用户数据路径管理
│   ├── chat_service.py         # AI 对话 + 记忆系统
│   ├── status_panel.py         # 个人中心面板
│   ├── knowledge_hub.py        # 知识中心窗口
│   ├── pet_state.py            # 宠物状态
│   ├── game_systems.py         # 游戏系统
│   ├── pet_animator.py         # 动画状态机
│   ├── pet_renderer_sprite.py  # 精灵渲染（.pak 懒加载）
│   ├── pak_loader.py           # .pak 资源包解混淆
│   ├── bubble_widget.py        # 气泡消息
│   ├── input_monitor.py        # 键鼠监控
│   └── web_crawler.py          # 网页爬取
├── assets/
│   ├── animations/             # 动画资源包（.pak）
│   └── items/                  # 道具动画资源包（.pak）
└── icons/                      # 图标资源
```

## License

MIT
