# 研究方向配置系统 (v2.16.2)

> 被 SKILL.md 的 §Skill概述 与 Phase 0 (`/init`) 引用。设研究方向用 `set-field --field [id]`；查可用配置列表、自定义方法、config_manager 用法时 `Read` 本文件。

## 配置文件位置
研究方向配置文件位于 `configs/` 目录：
```
configs/
├── _schema.json                 # JSON Schema 定义
├── default.json                 # 通用默认配置
├── biomedical_pharma.json      # 医药领域总默认
├── drug_delivery.json          # 药物递送系统
├── clinical_pharmacy_llm.json  # 临床药学和大模型交叉学科
├── computer_science.json       # 计算机科学
└── quantitative_pharmacology.json  # 定量药理学
```

## 可用研究方向

| 配置ID | 名称 | 说明 |
|--------|------|------|
| `default` | 通用学术论文 | 适用于大多数学科 |
| `biomedical_pharma` | 医药领域研究 | 医药总配置，覆盖材料学、药理、机制、临床等广义医药研究 |
| `drug_delivery` | 药物递送系统 | 纳米载体、细菌递送、外泌体、病毒载体等 |
| `clinical_pharmacy_llm` | 临床药学和大模型 | 临床药学、AI交叉 |
| `computer_science` | 计算机科学 | 机器学习、系统等 |
| `quantitative_pharmacology` | 定量药理学 | PK/PD建模等 |

## 使用配置管理器

```bash
# 列出所有可用研究方向
python scripts/config_manager.py list

# 加载指定配置
python scripts/config_manager.py load --field drug_delivery

# 验证配置
python scripts/config_manager.py validate --field drug_delivery

# 创建自定义配置
python scripts/config_manager.py create --field my_field --name "我的研究领域"
```

## 用户自定义配置

用户可以在以下位置添加自定义配置：
1. 项目目录的 `configs/` 子目录
2. 用户目录 `~/.general-sci-writing/configs/`

自定义配置优先级高于内置配置。

## set-field 命令

在项目初始化时设置研究方向：
```
python scripts/state_manager.py set-field --field drug_delivery
```
设置后，系统将加载对应研究方向的审稿人质疑库、实验类型和写作规范。
