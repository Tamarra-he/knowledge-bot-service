#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识清单生成模块
功能：从帮助教程.md 内容生成 知识清单.xlsx
"""

import os
os.environ["NUMPY_EXPERIMENTAL_DTYPE_API"] = "1"

import re
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys

print("📦 knowledge_parser 模块加载中...")
sys.stdout.flush()


def extract_knowledge_id(url_or_text):
    """从URL或文本中提取知识ID"""
    patterns = [
        r'/doc/(\d+)',
        r'/help/doc/(\d+)',
        r'/article/(\d+)',
        r'/video/(\d+)',
        r'知识ID[：:]\s*(\d+)',
        r'ID[：:]\s*(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_text)
        if match:
            return int(match.group(1))
    return None


def parse_category_levels(category_str):
    """拆分多级分类"""
    if not category_str:
        return '', '', '', ''
    
    parts = [p.strip() for p in category_str.split('/')]
    software_name = parts[0] if len(parts) >= 1 else ''
    article_type = parts[1] if len(parts) >= 2 else ''
    third_category = parts[2] if len(parts) >= 3 else ''
    fourth_category = parts[3] if len(parts) >= 4 else ''
    
    if article_type:
        if '手册' in article_type:
            article_type = '文章'
        elif '视频' in article_type:
            article_type = '视频'
    
    return software_name, article_type, third_category, fourth_category


def parse_markdown_content(content_text):
    """
    解析Markdown内容，提取结构化知识数据
    支持两种格式：
    1. # 标题 + 分类：xx/xx/xx + 内容
    2. 原文链接：xxx + 分类：xx/xx/xx + 内容
    """
    lines = content_text.split('\n')
    data = []
    current_title = None
    current_category = None
    current_content = []
    in_title = False
    has_found_anything = False
    
    i = 0
    while i < len(lines):
        line = lines[i].strip() if i < len(lines) else ''
        
        # =========================================================
        # 方式1：检测 # 标题
        # =========================================================
        if re.match(r'^#{1}\s+', line) and not re.match(r'^#{2,}', line):
            has_found_anything = True
            # 保存上一条知识
            if current_title is not None:
                raw_content = '\n'.join(current_content).strip()
                software_name, article_type, third_category, fourth_category = parse_category_levels(current_category)
                
                data.append({
                    '标题': current_title,
                    '完整分类': current_category or '',
                    '软件名称': software_name,
                    '文章类型': article_type,
                    '三级分类': third_category,
                    '四级分类': fourth_category,
                    '内容': raw_content,
                    '视频标注': '有视频' if 'mp4' in raw_content.lower() else '无视频',
                    '知识ID': extract_knowledge_id(raw_content) or extract_knowledge_id(current_category)
                })
            
            current_title = re.sub(r'^#{1}\s+', '', line).strip()
            current_category = None
            current_content = []
            in_title = True
            i += 1
            continue
        
        # =========================================================
        # 方式2：检测 原文链接：
        # =========================================================
        link_match = re.match(r'^原文链接[：:]\s*(.*)$', line)
        if link_match and not current_title:
            has_found_anything = True
            # 保存上一条知识
            if current_content and current_title is None:
                # 尝试从内容中提取标题
                temp_content = '\n'.join(current_content).strip()
                temp_lines = temp_content.split('\n')
                temp_title = temp_lines[0] if temp_lines else "未命名"
                software_name, article_type, third_category, fourth_category = parse_category_levels(current_category)
                
                data.append({
                    '标题': temp_title,
                    '完整分类': current_category or '',
                    '软件名称': software_name,
                    '文章类型': article_type,
                    '三级分类': third_category,
                    '四级分类': fourth_category,
                    '内容': temp_content,
                    '视频标注': '有视频' if 'mp4' in temp_content.lower() else '无视频',
                    '知识ID': extract_knowledge_id(link_match.group(1))
                })
            
            current_title = None
            current_category = None
            current_content = []
            current_content.append(line)  # 保留原文链接行
            in_title = False
            i += 1
            continue
        
        # =========================================================
        # 检测分类行
        # =========================================================
        cat_match = re.match(r'^分类[:：]\s*(.*)$', line)
        if cat_match:
            current_category = cat_match.group(1).strip()
            # 如果当前没有标题，尝试从分类中提取软件名作为标题
            if current_title is None:
                parts = current_category.split('/')
                if parts:
                    current_title = parts[0].strip()
            i += 1
            continue
        
        # =========================================================
        # 检测分隔线
        # =========================================================
        if re.match(r'^---\s*$', line) or re.match(r'^===\s*$', line):
            if current_content or current_title:
                raw_content = '\n'.join(current_content).strip()
                if current_title is None:
                    temp_lines = raw_content.split('\n')
                    current_title = temp_lines[0] if temp_lines else "未命名"
                
                software_name, article_type, third_category, fourth_category = parse_category_levels(current_category)
                data.append({
                    '标题': current_title,
                    '完整分类': current_category or '',
                    '软件名称': software_name,
                    '文章类型': article_type,
                    '三级分类': third_category,
                    '四级分类': fourth_category,
                    '内容': raw_content,
                    '视频标注': '有视频' if 'mp4' in raw_content.lower() else '无视频',
                    '知识ID': extract_knowledge_id(raw_content) or extract_knowledge_id(current_category)
                })
            
            current_title = None
            current_category = None
            current_content = []
            in_title = False
            i += 1
            continue
        
        # =========================================================
        # 普通内容行
        # =========================================================
        if line:
            current_content.append(line)
        
        i += 1
    
    # =========================================================
    # 处理最后一条知识
    # =========================================================
    if current_content:
        raw_content = '\n'.join(current_content).strip()
        if raw_content:
            if current_title is None:
                temp_lines = raw_content.split('\n')
                current_title = temp_lines[0] if temp_lines else "未命名"
            
            # 检查是否包含原文链接但没有标题
            if '原文链接' in raw_content and current_title == "未命名":
                link_match = re.search(r'原文链接[：:]\s*(https?://[^\s]+)', raw_content)
                if link_match:
                    current_title = f"知识_{extract_knowledge_id(link_match.group(1))}" if extract_knowledge_id(link_match.group(1)) else "未命名"
            
            software_name, article_type, third_category, fourth_category = parse_category_levels(current_category)
            data.append({
                '标题': current_title,
                '完整分类': current_category or '',
                '软件名称': software_name,
                '文章类型': article_type,
                '三级分类': third_category,
                '四级分类': fourth_category,
                '内容': raw_content,
                '视频标注': '有视频' if 'mp4' in raw_content.lower() else '无视频',
                '知识ID': extract_knowledge_id(raw_content) or extract_knowledge_id(current_category)
            })
    
    return data


def generate_knowledge_list(md_content, original_filename=None):
    """
    生成知识清单Excel
    """
    try:
        print("=" * 60)
        print("📊 开始生成知识清单...")
        sys.stdout.flush()
        
        print(f"📄 内容长度: {len(md_content)} 字符")
        print(f"📄 内容前500字符:\n{md_content[:500]}")
        sys.stdout.flush()
        
        knowledge_data = parse_markdown_content(md_content)
        
        print(f"📊 解析完成，共 {len(knowledge_data)} 条知识")
        sys.stdout.flush()
        
        if not knowledge_data:
            return {
                "success": False,
                "error": f"未能解析出任何知识条目。请检查文档格式是否包含 # 标题或 原文链接。"
            }
        
        df = pd.DataFrame(knowledge_data)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("/app/data/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if original_filename:
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
