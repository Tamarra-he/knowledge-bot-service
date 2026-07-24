#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识月报数据生成（云端版）
支持通过参数指定月份和文件路径
"""

import re
import pandas as pd
import requests
import json
from pathlib import Path
from openpyxl.styles import Alignment, Font, PatternFill
from datetime import datetime
import os

# ===================== 配置区 =====================
# 从环境变量读取路径，如果没有则使用默认值
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output" / "reports"

# 确保目录存在
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 文件路径配置
MD_FILE = INPUT_DIR / "帮助教程.md"
READING_FILE = INPUT_DIR / "含阅读量列表.xlsx"
LAST_MONTH_FILE = INPUT_DIR / "上月帮助教程.xlsx"

# 飞书配置（可选）
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")

# ===================== 核心函数 =====================

def generate_monthly_report(year=None, month=None, output_path=None):
    """
    生成知识月报
    
    参数:
        year: 年份（如2026），默认当前月
        month: 月份（如7），默认当前月
        output_path: 输出文件路径，默认自动生成
    
    返回:
        dict: {"success": True/False, "file": "文件路径", "error": "错误信息"}
    """
    try:
        # 1. 确定月份
        if year is None or month is None:
            now = datetime.now()
            year = now.year
            month = now.month
        
        print(f"📊 开始生成 {year}年{month}月 知识月报...")
        
        # 2. 检查输入文件是否存在
        if not MD_FILE.exists():
            return {"success": False, "error": f"输入文件不存在: {MD_FILE}"}
        
        # 3. 解析MD文件
        df_know = parse_markdown_robust(MD_FILE)
        print(f"✅ MD解析完成，共 {len(df_know)} 条知识")
        
        # 4. 合并阅读量
        df_final = merge_reading_data(df_know, READING_FILE)
        print(f"✅ 阅读量合并完成")
        
        # 5. 合并上月数据
        if LAST_MONTH_FILE.exists():
            df_final = merge_last_month_data(df_final, LAST_MONTH_FILE)
            print(f"✅ 上月数据合并完成")
        else:
            print(f"⚠️ 上月数据文件不存在，跳过")
        
        # 6. 生成月报
        (overall_df, software_group, top10_df, add_detail_df, 
         del_detail_df, last_add_summary, last_add_curr_df, extra_metrics) = generate_monthly_report_detail(
            df_final, LAST_MONTH_FILE
        )
        print(f"✅ 月报数据生成完成")
        
        # 7. 保存Excel
        if output_path is None:
            output_path = OUTPUT_DIR / f"知识月报数据明细_{month}月.xlsx"
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df_final.to_excel(writer, sheet_name='知识清单_含阅读量', index=False)
            overall_df.to_excel(writer, sheet_name='月报整体指标', index=False)
            software_group.to_excel(writer, sheet_name='各软件维度统计', index=False)
            top10_df.to_excel(writer, sheet_name='各软件阅读量TOP10', index=False)
            
            if not add_detail_df.empty:
                add_detail_df.to_excel(writer, sheet_name='本月新增知识明细', index=False)
            if not del_detail_df.empty:
                del_detail_df.to_excel(writer, sheet_name='本月下线知识明细', index=False)
            if not last_add_summary.empty:
                last_add_summary.to_excel(writer, sheet_name='上月新增知识_本期汇总', index=False)
            if not last_add_curr_df.empty:
                last_add_curr_df.to_excel(writer, sheet_name='上月新增知识_本期明细', index=False)
        
        print(f"✅ 月报已保存: {output_path}")
        
        # 8. 返回结果
        return {
            "success": True,
            "file": str(output_path),
            "knowledge_count": len(df_final),
            "year": year,
            "month": month,
            "extra_metrics": extra_metrics
        }
        
    except Exception as e:
        print(f"❌ 月报生成失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ===================== 以下是你原来的所有函数 =====================
# （从你的 1.月报数据生成.py 中复制所有函数到这里）
# 包括：extract_knowledge_id, parse_markdown_robust, 
#        merge_reading_data, merge_last_month_data, 
#        generate_monthly_report_detail, 等等

# 注意：函数内部的路径需要改成使用变量，而不是硬编码
# 例如：md_file_path 改为作为参数传入

# ===================== 命令行入口 =====================
if __name__ == "__main__":
    # 如果直接运行，使用默认配置
    result = generate_monthly_report()
    if result["success"]:
        print(f"✅ 月报生成成功: {result['file']}")
        print(f"📊 知识总数: {result['knowledge_count']}")
    else:
        print(f"❌ 失败: {result['error']}")
