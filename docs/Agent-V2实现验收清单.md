# Agent V2 实现验收清单

> 对齐基准：《智能衣橱问答 Agent 设计方案》 v1.2。本文只记录已有代码和可重复验证，不把未运行的项目标为通过。

## 已实现且有自动验证

- 独立 FastAPI Agent Service、LangGraph 持久检查点、五路由、多任务 DAG 和有界计划。
- QuerySpec 1.0、Pydantic 严格 Schema、参数化 SQL、SQLGlot AST 白名单、强制 `user_id` 和只读连接边界。
- 单/双字段分组、最多三个聚合、应用层多值场合统计、真实 `total` 和分页 `has_more`。
- 外套、季节、场合、颜色和风格共享版本化 `values.yaml`。
- 四类合法穿搭模板、硬约束、固定权重评分、版本号、MMR 和小候选模型复核。
- DeepSeek JSON Output 适配、最多一次结构修复、受限降级；方舟文本与豆包视觉均使用 Responses API。
- 豆包图像固定 Schema、不确定字段、1 张限制、HTTPS/SSRF/MIME/10 MB 检查；本地上传以鉴权用户隔离的 `upload_id` 引用，仅调用模型时转 data URL，识别后可继续查个人衣橱。
- Open-Meteo 城市级实时天气工具、观测时间证据和失败降级。
- 最终回答 Schema、证据 ID、衣物 ID/图片、数字事实和待确认措辞校验。
- SSE 阶段事件、15 秒 heartbeat、90 秒运行上限、断开取消和会话 active run 取消。
- 结构化会话摘要、Top-8 相关长期记忆、逐轮异步 reviewer、10 回合 gate、冲突 supersede、用户查看/修改/删除。
- pending action 快照、LangGraph `interrupt/resume`、10 分钟过期、payload hash、`client_decision_id` 落库、行锁、事务、回查、重放幂等和并发冲突。
- Flask 与 Agent 统一 JWT 主体；旧 API 不再信任客户端 `user_id`；前端 token 只放 sessionStorage。
- MySQL run/tool 审计、路由、指纹、证据、token、延迟与状态；每个图节点和模型调用均在终端显示，并持久写入 `logs/agent.jsonl`，不记录正文和令牌。
- 旧图床真实探测返回 401 后，Agent 与兼容上传接口默认改用本地存储；仅显式设置 `IMAGE_STORAGE_MODE=superbed` 才尝试旧图床。
- 新旧服务并行，前端默认 Agent V2，旧 `/api/recommend` 保留作回滚。

## 可重复命令

```bash
/Users/gaolaotou/miniforge3/envs/tf_m1/bin/python -m py_compile backend/app.py
/Users/gaolaotou/Desktop/enter/envs/hello_agent/bin/python scripts/run_agent_smoke_tests.py
/Users/gaolaotou/Desktop/enter/envs/hello_agent/bin/python scripts/test_agent_e2e.py
/Users/gaolaotou/Desktop/enter/envs/hello_agent/bin/python scripts/test_agent_live.py
cd frontend && npm run build
```

`test_agent_e2e.py` 覆盖 SSE、计数正确性、推荐、确认恢复、重放、并发冲突、双用户隔离、摘要、审计、取消与 10 回合记忆 gate；所有测试会话、穿搭和临时用户都在结束时删除。

`test_agent_live.py` 在三个本地服务运行时调用真实 DeepSeek、豆包和 Open-Meteo，覆盖常用对话、多轮指代、提示注入、越权 ID、破坏性指令、请求上限、图片边界、旧图床本地回退、写操作确认隔离，以及终端/文件/数据库三层审计；合成用户、衣物、会话和图片会在结束时精确清理。

## 外部或人工门槛

- DeepSeek 和豆包端到端模型验收必须使用本机 `.env` 中的有效新 Key；不得把 Key 写入代码、文档或测试命令。
- 第 18.3 节的人工 Top-3 可接受率、路由 150 条等大规模黄金集阈值需要真实标注样本和 2–3 名评审，不用自动生成的同义改写伪造达标。
- 外部模型名、费率和配额继续作为环境配置；业务代码不写死价格。
