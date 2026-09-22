# 源码核对

检索archive/legacy_source_backup_20260908.zip内全部.py/.md/.txt文本，关键词SVC、SVM、rbf、support.vector、支持向量，未命中。备份保留不修改。这说明在本次备份范围没有找到可核验的SVM特征、标准化及参数；不能据此断言其他未提供文件从未有SVM。

因此当前SVM命名为“新定义的RBF-SVM基线”，不是旧模型复现。其底层使用scikit-learn 1.7.2 SVC（libsvm），特征及网格另在配置明确。

|用途|上游|固定版本|
|---|---|---|
|EEGNet作者原代码与DeepConvNet Keras参考|https://github.com/vlawhern/arl-eegmodels|4a512e503198db2010848813ead9afbf8cd54c97|
|实际训练EEGNet/Deep4Net PyTorch实现|https://github.com/braindecode/braindecode|官方PyPI 1.3.2源码发行包|
|实际训练SVC RBF实现|https://github.com/scikit-learn/scikit-learn|1.7.2，25dee604bae18205b01548348388baf7a1cdfe0e|
|TENT方法参考实现|https://github.com/DequanWang/tent|e9e926a668d85244c66a6d5c006efbd2b82e83e8|

Braindecode没有v1.3.2 Git标签，未把其他标签冒充同版；下载官方PyPI sdist并核验SHA256。实际使用的eegnet.py/deep4.py字节哈希与其一致。sklearn/svm/_classes.py仅Windows换行与GitHub不同，统一换行后的源码文本完全一致；验证脚本显式检查该差异。详细下载URL、归档SHA256在third_party/sources.json。

上游档案已经下载、解包，许可证仍在各源码包中。训练入口调用已安装的固定发行版；不是临时复制改名的自写架构，也不执行下载仓库的任意安装脚本。

TENT官方源码归档及原始`tent.py`保存在`third_party`并记录SHA256。EEG接入保持官方的一步测试熵最小化和仅更新BatchNorm仿射参数；由于EEGNet/Deep4Net含Dropout，适配入口显式保持Dropout为评估模式，避免将随机丢弃混入TENT效果。该协议差异已在独立配置和运行输出中记录。

核心来源：

- EEGNet: https://arxiv.org/abs/1611.08024
- DeepConvNet: https://arxiv.org/abs/1703.05051
- SVC参数接口: https://scikit-learn.org/1.7/modules/generated/sklearn.svm.SVC.html

模型实现与论文实验协议需区别：输入时长/采样率/训练划分和明确超参数以本项目配置为准。本轮目标是同一数据上的可靠Source Only基线，不声称复现论文原始分数。
