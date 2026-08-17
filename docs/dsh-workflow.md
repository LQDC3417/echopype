# DSH (DeepSeek Harness) 完整使用流程

## 流程图

```mermaid
flowchart TD
    Start([开始]) --> Install{是否已安装 DSH?}
    
    Install -->|否| NpxInstall["npx @deepseek-ai/dsh web"]
    NpxInstall --> AutoDownload["自动下载依赖（首次较慢）"]
    AutoDownload --> Installed["安装完成 ✅"]
    
    Install -->|是| Launch
    Installed --> Launch

    Launch["启动 DSH"] --> LaunchMethod{启动方式}
    
    LaunchMethod -->|Web 模式| WebCmd["npx @deepseek-ai/dsh web"]
    LaunchMethod -->|指定端口| WebPort["npx @deepseek-ai/dsh web --port 8080"]
    LaunchMethod -->|桌面端| Desktop["dsh-plugin-desktop"]
    
    WebCmd --> WaitServer["等待 Web 服务启动"]
    WebPort --> WaitServer
    Desktop --> WaitServer
    
    WaitServer --> ShowURL["终端显示访问地址<br/>http://127.0.0.1:PORT"]
    
    ShowURL --> OpenBrowser["打开浏览器访问该地址"]
    
    OpenBrowser --> MainScreen["进入主界面"]
    
    MainScreen --> ChooseAction{选择操作}
    
    ChooseAction -->|新建会话| NewSession["点击 ➕ 新建会话"]
    ChooseAction -->|继续旧会话| OldSession["从侧边栏选择历史会话"]
    ChooseAction -->|设置| Settings["配置 API Key / 模型 / 主题"]
    
    NewSession --> SetWorkspace["设置工作目录<br/>（项目所在路径）"]
    SetWorkspace --> InputMsg["在输入框发送消息"]
    OldSession --> InputMsg
    Settings --> MainScreen
    
    InputMsg --> AgentProcess["🤖 AI Agent 处理"]
    
    AgentProcess --> ToolUse{需要使用工具?}
    
    ToolUse -->|是| ExecTool["执行工具"]
    ExecTool --> ToolType{工具类型}
    
    ToolType -->|读写文件| FileOps["read / write / edit 文件"]
    ToolType -->|执行命令| ShellOps["pwsh / cmd 运行命令"]
    ToolType -->|搜索| WebSearch["web_search 搜索信息"]
    ToolType -->|子代理| SubAgent["subagent 委派任务"]
    ToolType -->|工作流| Workflow["workflow 多代理编排"]
    
    FileOps --> ToolResult["返回工具结果"]
    ShellOps --> ToolResult
    WebSearch --> ToolResult
    SubAgent --> ToolResult
    Workflow --> ToolResult
    
    ToolResult --> AgentProcess
    ToolUse -->|否| StreamReply["流式输出回复"]
    
    StreamReply --> UserResponse{用户响应}
    
    UserResponse -->|继续提问| InputMsg
    UserResponse -->|修改指令| InputMsg
    UserResponse -->|结束会话| SaveSession["会话自动保存"]
    
    SaveSession --> End([结束])

    style Start fill:#4CAF50,color:#fff
    style End fill:#f44336,color:#fff
    style ShowURL fill:#2196F3,color:#fff
    style AgentProcess fill:#9C27B0,color:#fff
    style ExecTool fill:#FF9800,color:#fff
```

## 命令行启动方式

### 方式 1：默认启动（推荐）
```cmd
npx @deepseek-ai/dsh web
```
启动后终端会显示访问地址，如 `http://127.0.0.1:3080`

### 方式 2：指定端口
```cmd
npx @deepseek-ai/dsh web --port 8080
```

### 方式 3：先切到项目目录再启动（推荐）
```cmd
cd D:\Administrator\Desktop\echopype
npx @deepseek-ai/dsh web
```

### 方式 4：查看帮助
```cmd
npx @deepseek-ai/dsh --help
npx @deepseek-ai/dsh web --help
```

## 三种启动模式对比

| 模式 | 命令 | 说明 |
|------|------|------|
| **Web 模式** | `npx @deepseek-ai/dsh web` | 纯浏览器访问，不需要 Electron |
| **桌面模式** | `dsh-plugin-desktop` | Electron 桌面应用，内嵌 Web 界面 |
| **Headless 模式** | `npx @deepseek-ai/dsh --profile headless "任务描述"` | 无界面，执行一次任务后退出 |

## 常用交互模式

| 模式 | 说明 | 触发方式 |
|------|------|----------|
| 普通对话 | 直接和 AI 对话 | 输入文字发送 |
| 技能 (Skill) | 加载特定技能指令 | AI 自动识别或手动触发 |
| 目标 (Goal) | 长期任务追踪 | AI 自动创建 |
| 工作流 (Workflow) | 多代理并行任务 | 用户明确要求 |
| 子代理 (Subagent) | 后台委派任务 | AI 自动委派 |

## 注意事项

1. **首次启动较慢**：`npx` 需要下载依赖包，后续启动会快很多
2. **工作目录**：DSH 的文件操作都在工作目录内进行，启动前 `cd` 到项目目录
3. **会话日志**：每次对话自动保存，异常关闭可能导致日志损坏
4. **权限策略**：默认 ask（需确认），可改为 never（自动批准）或 danger-full-access
5. **Shell 环境**：默认使用 PowerShell，支持 cmd 回退
