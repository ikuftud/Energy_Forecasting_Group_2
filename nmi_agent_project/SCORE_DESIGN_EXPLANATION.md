# NMI Forecastability Score 设计说明

这份说明解释 `EDA_Tasks/nmi_score_classification_threshold.py` 里几个核心 score 的设计逻辑：

```text
performance_score
data_quality_score
history_score
temporal_pattern_score
stability_score
mapping_score
```

这些分数都会被标准化到 0 到 1 之间。越接近 1，说明这个 NMI 在这个维度上越适合做预测；越接近 0，说明风险越高或预测难度越大。

## 总体流程

脚本先为每个 NMI 计算一批诊断指标，比如 baseline WAPE、缺失率、0 值比例、历史长度、周期性、稳定性和建筑映射质量。

然后把这些原始指标转换成 6 个 component score：

```text
performance_score       预测误差表现
data_quality_score      数据质量
history_score           历史长度和近期覆盖
temporal_pattern_score  时间规律强度
stability_score         用电模式稳定性
mapping_score           NMI 和建筑映射可信度
```

最后用加权平均得到总分：

```text
forecastability_score
```

默认权重是：

```text
performance_score       35%
data_quality_score      20%
history_score           15%
temporal_pattern_score  15%
stability_score         10%
mapping_score            5%
```

如果某个 component 缺失，比如某个 NMI 没有足够历史做 WAPE 回测，脚本会自动用剩下的非空 component 重新归一化权重，不会直接让总分变成空值。

## performance_score

`performance_score` 衡量这个 NMI 用简单 baseline 是否已经能预测得比较好。

脚本会测试三个 baseline：

```text
lag48      昨天同一半小时
lag336     上周同一半小时
calendar   相同星期几 + 相同半小时的历史平均
```

每个 baseline 都用 WAPE 作为误差指标：

```text
WAPE 越低，预测越好。
```

脚本记录三个 baseline 中最低的误差：

```text
best_baseline_WAPE
```

然后用 min-max 方式把 WAPE 转成 0 到 1：

```text
WAPE 最低的 NMI -> performance_score 接近 1
WAPE 最高的 NMI -> performance_score 接近 0
```

设计理由：如果一个 NMI 连简单的 lag/calendar baseline 都能预测得不错，说明它本身规律比较清楚，适合进入后续 forecasting model。

## data_quality_score

`data_quality_score` 衡量原始读数是否干净、连续、可靠。

它由 4 个子分数平均得到：

```text
missing_score
zero_score
zero_run_score
outlier_score
```

### missing_score

来自 `missing_rate`。

缺失率越低，分数越高。脚本使用固定阈值，而不是相对排名：

```text
missing_rate <= 0.001 -> 1.00
missing_rate <= 0.010 -> 0.90
missing_rate <= 0.050 -> 0.75
missing_rate <= 0.100 -> 0.50
missing_rate <= 0.200 -> 0.25
更高                  -> 0.05
```

### zero_score

来自 `zero_rate`。

0 值比例越低，分数越高。大量 0 值通常说明电表停用、数据中断，或者这个 NMI 不适合单独预测。

### zero_run_score

来自 `longest_zero_run_hours`。

它看最长连续 0 值持续了多少小时。短暂的 0 不一定严重，但很长的连续 0 往往代表停用或数据问题。

### outlier_score

来自 `outlier_rate`。

异常值比例越低，分数越高。异常值用 IQR 规则识别。

设计理由：数据质量有明确业务含义，所以这里用固定阈值更直观。比如缺失率 20% 就应该被明显惩罚，不应该只看它在所有 NMI 里的相对排名。

## history_score

`history_score` 衡量这个 NMI 是否有足够长、足够近、足够可验证的历史数据。

它由 3 个子分数平均得到：

```text
active_years_score
recent_coverage_score
validation_months_score
```

### active_years_score

来自 `active_years`。

active window 是从第一个非 0 读数到最后一个非 0 读数。历史越长，分数越高。

### recent_coverage_score

来自 `recent_coverage_24m`。

它衡量最近 24 个月里这个 NMI 是否还有有效读数。近期覆盖越好，说明它更适合当前预测任务。

### validation_months_score

来自 baseline 回测阶段的 `validation_months`。

可验证月份越多，说明 WAPE 评估越可靠。

这三个子分数使用 percentile score。也就是说，一个 NMI 的历史长度会和其他 NMI 相比，排名越靠前分数越高。

设计理由：历史维度没有一个绝对完美阈值。比如 4 年和 5 年的差别，不像 missing rate 那样有明确业务红线，所以用相对排名更稳。

## temporal_pattern_score

`temporal_pattern_score` 衡量用电序列有没有可学习的时间规律。

它由这些子分数平均得到：

```text
lag_48_score
lag_336_score
daily_cycle_score
weekly_pattern_score
seasonality_score
```

### lag_48_score

来自 `lag_48_corr`。

48 个半小时等于 1 天，所以它衡量“今天这个时间”和“昨天同一时间”是否相似。

### lag_336_score

来自 `lag_336_corr`。

336 个半小时等于 7 天，所以它衡量“今天这个时间”和“上周同一时间”是否相似。

### daily_cycle_score

来自 `daily_cycle_strength`。

它看一天内不同时间段的平均负荷是否有稳定形状。比如办公楼白天高、晚上低，就是明显 daily cycle。

### weekly_pattern_score

来自 `weekly_pattern_strength`。

它看 weekday/weekend 或不同星期几之间是否存在稳定差异。

### seasonality_score

来自 `seasonality_strength`。

它看不同月份或季节是否有稳定变化。

这些子分数也用 percentile score。规律越强，在所有 NMI 里排名越高，分数越高。

设计理由：时间规律越强，模型越容易学到重复模式，forecasting 的稳定性通常也更好。

## stability_score

`stability_score` 衡量这个 NMI 的用电模式是否稳定。

它由 3 个子分数平均得到：

```text
trend_score
yearly_variation_score
structural_break_score_scaled
```

### trend_score

来自 `trend_strength`。

趋势越强，说明长期负荷水平变化越明显。这里是越小越好，所以 score 会反向计算。

### yearly_variation_score

来自 `yearly_variation`。

年度之间变化越大，说明这个 NMI 的模式越不稳定。这里也是越小越好。

### structural_break_score_scaled

来自 `structural_break_score`。

它用 rolling mean 的最大变化衡量是否出现过明显结构突变。突变越大，分数越低。

设计理由：稳定性不是说完全不能变化，而是希望变化不要过于剧烈。如果 NMI 的用电模式经常断崖式变化，模型基于历史学到的规律就更容易失效。

## mapping_score

`mapping_score` 衡量 NMI 和建筑物之间的映射是否清楚。

脚本先从多个来源合并映射：

```text
building_nmi_mapping.json
LMS Serial to NMI Map.xlsx
Parkville Substation Mapping.xlsx
Archibus building metadata
```

然后给每个 NMI 一个 `mapping_quality`，再映射成分数：

```text
one_building_mapped                 -> 1.00
many_to_one                         -> 0.80
multi_building_mapped               -> 0.65
substation_shared_multi_building    -> 0.55
many_to_many                        -> 0.45
unknown                             -> 0.30
unmapped                            -> 0.20
```

设计理由：映射越清楚，越容易解释预测结果，也越容易把 building type、campus、operation pattern 等信息用于建模。映射混乱不一定代表时间序列完全不可预测，但会降低单独建模和业务解释的可靠性，所以权重只给 5%。

## 最终分类怎么用这些 score

脚本不是直接按总分硬切所有 NMI。它先用 hard rules 处理明显不适合的情况。

### Exclude / Needs Review

满足下面任意条件，会直接进入 `Exclude / Needs Review`：

```text
status 是 Dead 或 Mostly inactive
active_years < 0.25
zero_rate >= 0.80
```

这些属于严重数据或活跃性问题，不适合只靠总分排序。

### Tier C - Short-history candidate

如果没有被 exclude，但满足下面任意条件，会进入 Tier C：

```text
active_years < 1.0
validation_months < 3
best_baseline_WAPE 缺失
```

Tier C 不一定代表数据差，而是历史不够长，或者 backtesting 不够可靠。更适合 pooled/global model。

### Tier A / B / D

剩下的 eligible NMI 才按 `forecastability_score` 分位数分类：

```text
score >= q75 -> Tier A - Strong forecasting candidate
score <= q25 -> Tier D - Difficult forecasting candidate
其他         -> Tier B - Usable with caution
```

设计理由：先把明显不可用和短历史 NMI 分出来，再对真正可比较的 NMI 做相对排序。这样 Tier A/B/D 的含义会更稳定。

## 哪些部分后续被 tuning agent 调整

这个 threshold 脚本给出的是初始规则版本。后续 `score_tuning_agent` 和 `final_test_driver` 主要调这些部分：

```text
6 个 component 的权重
data quality 的 strict/base/lenient 阈值 profile
Tier D 和 Tier A 的分位数切点
```

也就是说，初始脚本负责给出一个可解释的 baseline 分类；后续 tuning 用 CV review 的反馈去微调它，让最终分类更符合人工视觉审查结果。
