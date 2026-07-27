#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识清单生成模块
功能：从帮助教程.md 内容生成 知识清单.xlsx
"""

import re
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys

print("📦 knowledge_parser 模块加载中...")
sys.stdout.flush()


def parse_markdown_content(content_text):
    """
    解析Markdown内容，提取结构化知识数据
    
    参数:
        content_text: 帮助教程.md 的文本内容
    
    返回:
        list: 知识条目列表，每条包含：标题、分类、内容、知识ID等
    """
    lines = content_text.split('\n')
    data = []
    current_title = None
    current_category = None
    current_content = []
    in_title = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 检测一级标题（# 标题）
        if re.match(r'^#{1}\s+', line) and not re.match(r'^#{2,}', line):
            # 保存上一条知识
            if current_title is not None:
                raw_content = '\n'.join(current_content).strip()
                content_cleaned = remove_original_link_line(raw_content)
                has_video = 'mp4' in content_cleaned.lower()
                knowledge_id = extract_knowledge_id(raw_content)
                software_name, article_type, third_category, fourth_category = parse_category_levels(current_category)
                
                data.append({
                    '标题': current_title,
                    '完整分类': current_category or '',
                    '软件名称': software_name,
                    '文章类型': article_type,
                    '三级分类': third_category,
                    '四级分类': fourth_category,
                    '内容': content_cleaned,
                    '视频标注': '有视频' if has_video else '无视频',
                    '知识ID': knowledge_id
                })
            
            # 开始新知识
            current_title = re.sub(r'^#{1}\s+', '', line).strip()
            current_category = None
            current_content = []
            in_title = True
            i += 1
            continue
        
        # 如果在标题内，检查分类行
        if in_title and current_title is not None:
            # 检测分类行
            cat_match = re.match(r'^分类[:：]\s*(.*)$', line)
            if cat_match:
                current_category = cat_match.group(1).strip()
                i += 1
                continue
            
            # 检测分隔线 ---
            if re.match(r'^---\s*$', line):
                if current_title is not None:
                    raw_content = '\n'.join(current_content).strip()
                    content_cleaned = remove_original_link_line(raw_content)
                    has_video = 'mp4' in content_cleaned.lower()
                    knowledge_id = extract_knowledge_id(raw_content)
                    software_name, article_type, third_category, fourth_category = parse_category_levels(current_category)
                    
                    data.append({
                        '标题': current_title,
                        '完整分类': current_category or '',
                        '软件名称': software_name,
                        '文章类型': article_type,
                        '三级分类': third_category,
                        '四级分类': fourth_category,
                        '内容': content_cleaned,
                        '视频标注': '有视频' if has_video else '无视频',
                        '知识ID': knowledge_id
                    })
                
                current_title = None
                current_category = None
                current_content = []
                in_title = False
                i += 1
                continue
            
            # 普通内容行
            current_content.append(line)
        
        i += 1
    
    # 处理最后一条知识（如果没有以 --- 结尾）
    if current_title is not None:
        raw_content = '\n'.join(current_content).strip()
        content_cleaned = remove_original_link_line(raw_content)
        has_video = 'mp4' in content_cleaned.lower()
        knowledge_id = extract_knowledge_id(raw_content)
        software_name, article_type, third_category, fourth_category = parse_category_levels(current_category)
        
        data.append({
            '标题': current_title,
            '完整分类': current_category or '',
            '软件名称': software_name,
            '文章类型': article_type,
            '三级分类': third_category,
            '四级分类': fourth_category,
            '内容': content_cleaned,
            '视频标注': '有视频' if has_video else '无视频',
            '知识ID': knowledge_id
        })
    
    return data


def extract_knowledge_id(content_text):
    """从文章内容中提取知识ID（原文链接最后的数字）"""
    patterns = [
        r'原文链接[：:]\s*https?://[^\s]+/doc/(\d+)',
        r'原文链接[：:]\s*https?://[^\s]+/help/doc/(\d+)',
        r'原文链接[：:]\s*https?://[^\s]+/article/(\d+)',
        r'原文链接[：:]\s*https?://[^\s]+/video/(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, content_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def remove_original_link_line(content_text):
    """移除内容中的原文链接行"""
    lines = content_text.split('\n')
    filtered_lines = []
    for line in lines:
        if re.search(r'原文链接[：:]\s*https?://', line, re.IGNORECASE):
            continue
        filtered_lines.append(line)
    return '\n'.join(filtered_lines).strip()


def parse_category_levels(category_str):
    """拆分多级分类"""
    if not category_str:
        return '', '', '', ''
    
    parts = [p.strip() for p in category_str.split('/')]
    software_name = parts[0] if len(parts) >= 1 else ''
    article_type = parts[1] if len(parts) >= 2 else ''
    third_category = parts[2] if len(parts) >= 3 else ''
    fourth_category = parts[3] if len(parts) >= 4 else ''
    
    # 标准化文章类型
    if article_type:
        if '手册' in article_type:
            article_type = '文章'
        elif '视频' in article_type:
            article_type = '视频'
    
    return software_name, article_type, third_category, fourth_category


def generate_knowledge_list(md_content, original_filename=None):
    """
    生成知识清单Excel
    
    参数:
        md_content: 帮助教程.md 的文本内容
        original_filename: 原始文件名（用于生成输出文件名）
    
    返回:
        dict: {
            "success": True/False,
            "file_path": "输出文件路径",
            "count": 知识条数,
            "error": "错误信息"
        }
    """
    try:
        print("📊 开始生成知识清单...")
        sys.stdout.flush()
        
        # 1. 解析MD
        knowledge_data = parse_markdown_content(md_content)
        
        if not knowledge_data:
            return {
                "success": False,
                "error": "未能解析出任何知识条目，请检查文件格式是否正确"
            }
        
        print(f"📊 解析完成，共 {len(knowledge_data)} 条知识")
        sys.stdout.flush()
        
        # 2. 转换为DataFrame
        df = pd.DataFrame(knowledge_data)
        
        # 3. 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("/app/data/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if original_filename:
            # 从原始文件名提取月份信息
            month_match = re.search(r'(\d{4})[-_](\d{1,2})', original_filename)
            if month_match:
                year = month_match.group(1)
                month = month_match.group(2)
                filename = f"知识清单_{year}年{month}月.xlsx"
            else:
                filename = f"知识清单_{timestamp}.xlsx"
        else:
            filename = f"知识清单_{timestamp}.xlsx"
        
        output_path = output_dir / filename
        
        # 4. 保存Excel
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='知识清单', index=False)
        
        print(f"✅ 知识清单已保存: {output_path}")
        sys.stdout.flush()
        
        return {
            "success": True,
            "file_path": str(output_path),
            "filename": filename,
            "count": len(df),
            "columns": df.columns.tolist()
        }
        
    except Exception as e:
        print(f"❌ 生成知识清单失败: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return {
            "success": False,
            "error": str(e)
        }


print("✅ knowledge_parser 模块加载完成")
sys.stdout.flush()
