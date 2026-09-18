# 场景路由

| scenes 值 | 识别线索 | 模板 |
|---|---|---|
| meeting | 多方讨论、议题、进度、决策 | templates/meeting.md |
| interview | 研究者提问，受访者讲述使用经历 | templates/interview.md |
| customer | 需求、服务、报价、采购异议 | templates/customer.md |
| recruitment | 岗位面试、经历与能力问答 | templates/recruitment.md |
| learning | 知识讲解、培训、课堂、播客 | templates/learning.md |
| personal | 自我记录、想法、个人事项 | templates/personal.md |
| general | 无法分类或复杂混合 | templates/general.md |

多场景允许数组，不强求单一标签。同一场景模板字段没有证据就不填满。场景专属内容存入 topics，标题表达用途；决策和行动各归专属数组，避免重复。

当招聘面试与研究访谈混淆等会影响用途时，先询问用户；普通会议夹杂简短知识讲解不需要来回确认。
