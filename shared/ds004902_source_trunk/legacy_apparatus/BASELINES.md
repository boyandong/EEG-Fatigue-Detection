# 三模型 Source Only 实验

第一阶段数据不变：68人、9390段，61通道×2000点，500 Hz、4秒，标签0正常睡眠/1睡眠剥夺条件。5000 Hz记录及缺配对受试者排除；PVT不参与。

## 按顺序执行

1. **源码核对与下载**：已完成，详见SOURCE_AUDIT.md、third_party/sources.json。原始许可证保存在解包目录。
2. **本地程序检查**：运行smoke，仅每人每场次前2段、sub-01测试、seed=0、神经网络2轮。这些结果只验证流程，不能用来挑模型或宣称准确率。
3. **AutoDL三人试跑**：固定sub-01/02/03，seed=0，三模型均使用完整训练/验证/测试片段。神经网络最多50轮，验证“逐受试者平均Balanced Accuracy”早停，patience=10。SVM验证选择9组C/gamma。试跑在AutoDL执行，预算100元，先不启动正式实验。
4. **检查训练诊断并锁配置**：看损失、验证曲线、预测分布、过拟合和耗时。不能按测试效果改架构或阈值；若使用试跑测试成绩调整配置，这3人后续只能视为开发受试者，不再宣称其正式测试无偏。
5. **正式LOSO**：确认资源与锁定配置后才运行。68人×3神经种子；SVM每折一次。formal入口必须传入配置SHA256，不会从pilot自动进入formal。100元不能未经估算就承诺覆盖全部正式实验。

## 入口

```powershell
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 project/run_baselines.py --stage smoke --run-name smoke_v3
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 project/verify_baselines.py --run-root project/results/smoke_v3
```

每个模型可用 `--models eegnet`、`--models deepconvnet` 或 `--models rbf_svm` 单独执行。`--data-root`支持移动数据。相同运行名支持跳过已完成的模型/折/种子；代码、环境、配置或数据变更必须换运行名。未完成的单折从头训练，不冒充精确断点续训。

## 模型与参数定义

- EEGNet：Braindecode 1.3.2 EEGNet-8,2,16。temporal kernel=250点（0.5秒），separable depthwise kernel=64点（0.128秒），为500 Hz明确定义的时间尺度；不是机械采用128 Hz示例的64点。Dropout=0.5，带约束分类层。
- DeepConvNet：Braindecode 1.3.2 Deep4Net，4卷积块25/50/100/200，kernel=10点、pool=3、Dropout=0.5；保留上游默认采样点超参数，不宣称逐项复现论文训练协议。
- 两网络仅以训练人波形计算每通道全局mean/std，固定应用于验证/测试；Adam lr=0.001，batch=32，交叉熵，FP32，固定随机种子与确定性算法。
- **新定义RBF-SVM基线**：同一原波形做Welch（500 Hz、Hann 1000点、overlap500、constant detrend、density、mean），按[1,4]、[4,8]、[8,13]、[13,30]、[30,45] Hz闭区间梯形积分，log10(max(power,1e-12))，通道优先展开成305特征。StandardScaler仅训练拟合，无特征选择。C={0.1,1,10}，gamma={scale,0.001,0.01}，class_weight=balanced，probability=False，tol=0.001，无迭代上限。并列验证分数取配置中首组。

## Source Only核验

神经网络test调用eval和inference_mode；测试前后整个state_dict（含BN缓冲）SHA256一致；重复推理逐点相同。标准化由train独立拟合，保存normalization.npz。SVM是训练人拟合的Pipeline，测试前后joblib哈希一致。无TTA，无测试分布重估。原有EEGLAB预处理的历史限制仍存在。

## 输出与runtime口径

每模型/受试者/种子目录保存result.json、predictions.csv、segment_membership.csv和split.json；网络另存best.pt、normalization.npz、history.csv、curves.png；SVM另存model.joblib、svm_search.csv。

Accuracy、Balanced Accuracy、F1(正类1)、ROC-AUC均逐测试人计算。AUC使用概率或decision_function，不用0/1预测。汇总表区分：每种子的受试者均值/受试者间SD、每人的种子均值/SD、先种子平均后的受试者间SD、种子级受试者均值的SD。只有一个种子时SD留空，不填0。

runtime单位秒，时钟perf_counter，GPU边界同步。记录训练人标准化拟合、每轮训练/验证、含验证与检查点的训练过程、测试推理、每段推理毫秒、冻结核验、训练诊断、模型总耗时、GPU峰值显存。SVM还记录各组fit/validation、特征提取、测试特征+推理端到端。神经测试推理含数据加载、固定标准化与传输；SVM纯推理不含特征提取，比较端到端时必须另加该项。

共用的数据哈希校验/加载计时单独保存，不重复记入三个模型。模型总耗时含首次依赖初始化，且只有小样本，不能将smoke总时间作性能排名；正式runtime比较应在同一服务器上进行。provenance保存GPU、OS、库版本、代码、配置、划分、片段与上游来源哈希。
