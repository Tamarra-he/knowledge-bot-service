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
    解析Markdown内容，按原文链接分割知识块
    格式：
    标题1
    原文链接：https://...
    分类：xx/xx/xx
    内容...
    
    标题2
    原文链接：https://...
    分类：xx/xx/xx
    内容...
    """
    lines = content_text.split('\n')
    data = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip() if i < len(lines) else ''
        
        # 检测原文链接行
        link_match = re.match(r'^原文链接[：:]\s*(https?://[^\s]+)', line)
        if link_match:
            link_url = link_match.group(1)
            knowledge_id = extract_knowledge_id(link_url)
            
            # 提取标题（原文链接的上一行非空行）
            title = "未命名"
            j = i - 1
            while j >= 0:
                prev_line = lines[j].strip() if j < len(lines) else ''
                if prev_line and not re.match(r'^原文链接[：:]', prev_line) and not re.match(r'^分类[：:]', prev_line):
                    # 检查是否是标题（不以数字开头，不太长）
                    if not re.match(r'^[\d]+[）).]', prev_line) and len(prev_line) < 100:
                        title = prev_line
                        break
                j -= 1
            
            # 提取分类
            category = ""
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip() if j < len(lines) else ''
                cat_match = re.match(r'^分类[：:]\s*(.*)$', next_line)
                if cat_match:
                    category = cat_match.group(1).strip()
                    break
                j += 1
            
            # 提取内容（从分类之后到下一个原文链接之前）
            content_parts = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip() if j < len(lines) else ''
                # 如果遇到下一个原文链接，停止
                if re.match(r'^原文链接[：:]\s*https?://', next_line):
                    break
                # 跳过分类行本身
                if not re.match(r'^分类[：:]\s*', next_line):
                    if next_line:
                        content_parts.append(next_line)
                j += 1
            
            content = '\n'.join(content_parts).strip()
            
            # 解析分类层级
            software_name, article_type, third_category, fourth_category = parse_category_levels(category)
            
            # 检测是否有视频
            has_video = 'mp4' in content.lower() or '视频' in content
            
            data.append({
                '标题': title,
                '完整分类': category,
                '软件名称': software_name,
                '文章类型': article_type,
                '三级分类': third_category,
                '四级分类': fourth_category,
                '内容': content,
                '视频标注': '有视频' if has_video else '无视频',
                '知识ID': knowledge_id
            })
            
            # 跳到下一个原文链接的位置
            i = j
        else:
            i += 1
    
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
        
        # 统计原文链接数量
        link_count = len(re.findall(r'原文链接[：:]\s*https?://', md_content))
        print(f"📊 检测到 {link_count} 个原文链接")
        sys.stdout.flush()
        
        knowledge_data = parse_markdown_content(md_content)
        
        print(f"📊 解析完成，共 {len(knowledge_data)} 条知识")
        sys.stdout.flush()
        
        if not knowledge_data:
            return {
                "success": False,
                "error": "未能解析出任何知识条目，请检查文档格式"
            }
        
        # 打印前3条预览
        for idx, item in enumerate(knowledge_data[:3]):
            print(f"  [{idx+1}] 标题: {item['标题']}, ID: {item['知识ID']}, 分类: {item['完整分类']}")
        sys.stdout.flush()
        
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
