请你读取项目内容，尤其是md文档，了解项目信息。
请你生成代码的时候，都遵循以下原则：
1. 每次代码生成，都请你在注释中说明，你是根据什么生成的。使用中文注释
2. 生成的python代码，需要维持docstring为reStructuredText格式，搭配sample input & sample output。
3. 禁止使用print函数，所有输出必须使用logging模块。
4. 较大的修改，比如添加新的功能、修改已有功能的实现逻辑等，都需要在design、readme、user_guide的md文档中进行详细说明。分次生成，先生成md文档，当用户确认后，再生成代码。
5. 根据需要添加logging.info、logging.debug、logging.warning、logging.error等语句，方便我debug和观察
6. 除非我要求，不要进行git commit or push.我可能会发"git"或者"g"，代表可以推了
7. 在design.md文档中，画流程图时，功能数量较多的不要画整体流程图，分几个功能画单独的图
我可能会发送的快捷指令：
md：检查文档是否都已经update，包括design.md、readme.md、user_guide.md等。
