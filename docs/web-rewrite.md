# Web 前端重构记录

## 文档信息

- **版本**: 1.0
- **重构日期**: 2026-04-14
- **状态**: 已完成

## 重构目标

将 Web 前端从 Vue 3 迁移到 React 19，重建 UI 设计系统，提升视觉品质和开发体验。

## 重构动机

1. **生态选择**: React 生态（shadcn/ui、Radix、Framer Motion）在组件质量、TypeScript 支持、社区活跃度上优于 Vue
2. **UI 品质**: 原 Vue 端 UI 粗糙，缺乏设计语言，无动画体系
3. **代码质量**: 原代码无统一的类型定义、状态管理模式和 API 抽象
4. **产品定位**: AI-Link-Net 作为去中心化 AI 协作协议，需要与产品调性匹配的"Precision Craft"设计语言

## 三阶段执行计划

### Phase 1: 基础设施（已完成）

| 任务 | 说明 |
|------|------|
| 清理 Vue 代码 | 移除所有 Vue 源码、配置、依赖 |
| React + Vite + TS 初始化 | Vite 8 + React 19 + TypeScript 6 |
| Tailwind CSS 4 + shadcn/ui | New York 风格，10 个基础 UI 组件 |
| 设计系统 | CSS tokens（色彩/字体/动画），globals.css |
| API client | Axios 实例 + 拦截器（auth/401），5 个 API 模块 |
| 类型定义 | 全量 TypeScript 类型（Entity/Contact/Message/Mail/Session） |
| Zustand store | 应用状态管理（auth/contacts/unread） |
| React Router | 4 个路由 + ProtectedRoute 守卫 |
| MainLayout | 桌面侧边栏 + 移动端汉堡菜单 |

### Phase 2: 核心页面（已完成）

| 页面 | 功能 |
|------|------|
| Login | 保存账户列表、Host 连接、实体选择、URL 参数自动登录 |
| Chat | 消息历史加载、WebSocket 实时通信、联系人列表、会话管理、好友删除、已读标记 |
| Discover | 实体发现、好友添加、过滤已有好友、刷新 |
| Register | 实体注册（Agent/Human/Tool）、Provider 选择（Claude/Codex/Autowork）、高级配置（trust_level/model/workdir） |

### Phase 3: 美学打磨（已完成）

| 任务 | 说明 |
|------|------|
| 视觉效果组件 | NetworkParticles（粒子网络动画）、GradientOrb（渐变光晕） |
| Login 页重设计 | 粒子网络背景、品牌渐变、玻璃态卡片、Stagger 入场动画 |
| Chat 页打磨 | 消息气泡渐变边框、状态语义图标、联系人 Stagger 动画、品牌网络空状态 |
| Discover/Register 打磨 | 卡片浮入动画、hover 上浮效果、accent 色阴影 |
| 全局动画体系 | 统一贝塞尔曲线 `[0.21, 0.47, 0.32, 0.98]`、Framer Motion variants |
| CSS 工具类 | `text-gradient`、`glass`、`gradient-border` |

## 技术栈变更

### 移除（Vue 时代）

```
vue 3.5, vue-router 4.2, pinia 2.1
```

### 新增（React 时代）

```
react 19.2           — UI 框架
react-dom 19.2       — DOM 渲染
react-router-dom 7   — 路由
zustand 5            — 状态管理
framer-motion 12     — 动画
shadcn/ui            — 组件库（基于 Radix UI）
class-variance-authority — 组件变体
lucide-react         — 图标
tailwindcss 4        — 样式（从 v3 升级）
clsx + tailwind-merge — 类名工具 (cn())
axios                — HTTP 客户端（保留）
typescript 6         — 类型系统（从 v5 升级）
vite 8               — 构建工具（从 v6 升级）
```

## 设计语言: "Precision Craft"

### 色彩系统

| Token | 值 | 用途 |
|-------|-----|------|
| Primary | `#8B5CF6` (Violet) | 智能、品牌主色 |
| Accent | `#06B6D4` (Cyan) | 连接、网络、Agent |
| Background | `#09090B` | 深色基底 |
| Surface | `rgba(255,255,255,0.05)` | 层次表面 |
| Success | `#10B981` | 消息已送达 |
| Warning | `#F59E0B` | 发送中/排队 |
| Destructive | `#EF4444` | 错误/删除 |

### 字体系统

| 用途 | 字体 | 说明 |
|------|------|------|
| Heading | Space Grotesk | 几何感、技术美学 |
| Body | Inter | 最佳 UI 可读性 |
| Mono | JetBrains Mono | 代码/UID/地址 |

### 动画规范

- 消息入场: 150ms ease-out, translateY(8px)
- 页面转场: 200ms ease-in-out
- 交互反馈: scale(0.98) press, scale(1.01) hover
- 在线状态: 2s infinite pulse
- 统一缓动: cubic-bezier(0.21, 0.47, 0.32, 0.98)

## 目录结构

```
aln/web/src/
├── api/                          # API 层
│   ├── client.ts                # Axios 实例 + 拦截器
│   ├── entity.ts                # Entity/Friends API (11 端点)
│   ├── friend.ts                # Friend API (add/delete)
│   ├── mail.ts                  # Message send/history/markRead
│   ├── session.ts               # Session CRUD
│   └── index.ts                 # 统一导出
├── components/
│   ├── chat/
│   │   ├── chat-area.tsx        # 聊天区域（消息列表+输入+会话面板）
│   │   ├── contact-list.tsx     # 联系人侧栏列表
│   │   ├── message-item.tsx     # 消息气泡（状态图标+token 用量）
│   │   └── session-panel.tsx    # 会话管理面板（创建/切换/重命名/删除）
│   ├── effects/
│   │   ├── network-particles.tsx # Canvas 粒子网络动画
│   │   └── gradient-orb.tsx     # 渐变光晕浮动效果
│   ├── layout/
│   │   └── main-layout.tsx      # 主布局（桌面侧栏+移动端导航）
│   ├── profile/
│   │   └── profile-dialog.tsx   # 资料编辑对话框（头像上传/删除）
│   └── ui/                      # shadcn/ui 组件 (10 个)
├── hooks/
│   └── use-websocket.ts         # WebSocket 连接管理
├── lib/
│   └── utils.ts                 # cn() 类名合并工具
├── pages/
│   ├── login.tsx                # 登录页（粒子背景+玻璃态卡片）
│   ├── chat.tsx                 # 聊天页（联系人+聊天区域）
│   ├── discover.tsx             # 发现页（实体发现+好友添加）
│   └── register.tsx             # 注册页（Provider+高级配置）
├── stores/
│   └── app.ts                   # Zustand 全局状态
├── styles/
│   └── globals.css              # 设计系统 CSS tokens
├── types/
│   ├── api.ts                   # API 类型定义
│   └── index.ts
├── main.tsx                     # 入口
└── router.tsx                   # 路由配置
```

## Bug 修复（重构中同步解决）

| Bug | 原因 | 修复方案 |
|-----|------|---------|
| Mail 状态不正确 | 用了 `/mail` 而非 `/messages/send`，缺 delivery_status 事件处理 | 改用正确 API，WebSocket 处理 delivery_status + status_update |
| Discover 刷新后不加载 | Vue 的 watch 依赖问题 | React useEffect 独立触发 fetch，contacts 仅用于计算过滤 |
| Discover 移动端适配 | 缺 grid-cols-1 和 padding | 响应式 grid + 自适应 padding |
| Register 缺 provider 选择 | 重构时遗漏 | 补齐 claude/codex/autowork 选择 + trust_level/model/workdir 配置 |

## 功能完整性验证

对照原 Vue 端全量功能清单，逐项验证：

| 功能模块 | 子功能 | 状态 |
|----------|--------|------|
| **Entity API** | list/get/discover/update/delete/avatar/card/friends/status | 全部实现 |
| **Friends API** | add/delete | 全部实现 |
| **Mail API** | send/history/markRead | 全部实现 |
| **Session API** | list/create/rename/delete | 全部实现 |
| **WebSocket** | ping/pong/new_message/delivery_status/status_update | 全部实现 |
| **Login** | 保存账户/Host 连接/实体选择/URL 自动登录 | 全部实现 |
| **Chat** | 历史消息/实时通信/状态追踪/会话管理/好友删除/已读标记 | 全部实现 |
| **Discover** | 实体发现/好友添加/过滤/刷新 | 全部实现 |
| **Register** | 类型选择/Provider/高级配置 | 全部实现 |
| **Profile** | 资料编辑/头像上传删除 | 全部实现 |
| **联系人** | 缓存/状态轮询/未读计数 | 全部实现 |
| **移动端** | 响应式布局/返回按钮/侧栏切换 | 全部实现 |

## 后续建议

1. **React Error Boundary**: 添加全局错误边界防止白屏
2. **代码分割**: 动态 import 页面组件减小首屏包体积
3. **性能优化**: 列表组件 React.memo + useMemo
4. **UI 持续打磨**: 用 visual-judge 方法论迭代评审
5. **会话管理 8 号任务**: 已实现基础 CRUD，后续可增强（会话内消息过滤、会话搜索）
