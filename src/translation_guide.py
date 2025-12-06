# src/translation_guide.py - v2.5.1
# Tác giả: Narga
# Chức năng: Module xử lý và tổng hợp các chỉ dẫn dịch thuật nâng cao
#            từ style_profile.json, glossary.csv, character_relations.csv
#            nằm trong thư mục prompts/instructions/.

import json
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any


class StyleProfile:
    """
    Lớp xử lý và format thông tin từ style_profile.json.
    
    Style profile chứa thông tin về văn phong, thể loại, tone, đặc điểm
    hội thoại và hướng dẫn dịch thuật tổng quát cho tác phẩm.
    """
    
    def __init__(self, style_data: Dict[str, Any]):
        """
        Khởi tạo StyleProfile từ dictionary đã parse từ JSON.
        
        Args:
            style_data (Dict): Dictionary chứa dữ liệu style profile
        """
        self.data = style_data
    
    def format_for_prompt(self) -> str:
        """
        Format style profile thành văn bản để chèn vào prompt.
        
        Returns:
            str: Văn bản mô tả style profile, format theo cấu trúc dễ đọc
        """
        lines = []
        
        # Thông tin tác phẩm
        if 'novel_info' in self.data:
            info = self.data['novel_info']
            lines.append("## THÔNG TIN TÁC PHẨM")
            lines.append(f"- Tên: {info.get('title', 'N/A')}")
            lines.append(f"- Tác giả: {info.get('author', 'N/A')}")
            lines.append(f"- Độ dài: {info.get('estimated_length', 'N/A')}")
            lines.append("")
        
        # Thể loại và bối cảnh
        if 'genre' in self.data:
            genre = self.data['genre']
            lines.append("## THỂ LOẠI & BỐI CẢNH")
            lines.append(f"- Thể loại chính: {genre.get('primary', 'N/A')}")
            
            if 'sub_genres' in genre and genre['sub_genres']:
                lines.append(f"- Thể loại phụ: {', '.join(genre['sub_genres'])}")
            
            if 'world_setting' in genre:
                lines.append(f"- Bối cảnh thế giới: {genre.get('world_setting')}")
            
            if 'power_system' in genre:
                lines.append(f"- Hệ thống sức mạnh: {genre.get('power_system')}")
            lines.append("")
        
        # Phong cách viết
        if 'writing_style' in self.data:
            style = self.data['writing_style']
            lines.append("## PHONG CÁCH VIẾT")
            
            for key, value in style.items():
                if isinstance(value, str):
                    # Chuyển snake_case thành Title Case
                    key_display = key.replace('_', ' ').title()
                    lines.append(f"- {key_display}: {value}")
            lines.append("")
        
        # Tone và không khí
        if 'tone' in self.data:
            tone = self.data['tone']
            lines.append("## TONE & KHÔNG KHÍ")
            
            for key, value in tone.items():
                if isinstance(value, str):
                    key_display = key.replace('_', ' ').title()
                    lines.append(f"- {key_display}: {value}")
            lines.append("")
        
        # Đặc điểm hội thoại
        if 'dialogue_characteristics' in self.data:
            dialogue = self.data['dialogue_characteristics']
            lines.append("## ĐẶC ĐIỂM HỘI THOẠI")
            lines.append(f"- Mức độ trang trọng: {dialogue.get('formality_level', 'N/A')}")
            lines.append(f"- Ngôn ngữ thời kỳ: {dialogue.get('time_period_language', 'N/A')}")
            
            if 'pronoun_patterns' in dialogue:
                lines.append("- Các đại từ nhân xưng:")
                pronouns = dialogue['pronoun_patterns']
                
                if 'first_person' in pronouns:
                    lines.append(f"  + Ngôi thứ nhất: {', '.join(pronouns['first_person'])}")
                if 'second_person' in pronouns:
                    lines.append(f"  + Ngôi thứ hai: {', '.join(pronouns['second_person'])}")
                if 'third_person' in pronouns:
                    lines.append(f"  + Ngôi thứ ba: {', '.join(pronouns['third_person'])}")
            lines.append("")
        
        # Hướng dẫn dịch thuật
        if 'translation_guidelines' in self.data:
            guidelines = self.data['translation_guidelines']
            lines.append("## HƯỚNG DẪN DỊCH THUẬT")
            
            if 'preserve' in guidelines and guidelines['preserve']:
                lines.append("### Cần Giữ Nguyên:")
                for item in guidelines['preserve']:
                    lines.append(f"- {item}")
            
            if 'adapt' in guidelines and guidelines['adapt']:
                lines.append("\n### Cần Điều Chỉnh:")
                for item in guidelines['adapt']:
                    lines.append(f"- {item}")
            
            if 'avoid' in guidelines and guidelines['avoid']:
                lines.append("\n### Cần Tránh:")
                for item in guidelines['avoid']:
                    lines.append(f"- {item}")
            
            if 'priorities' in guidelines and guidelines['priorities']:
                lines.append("\n### Thứ Tự Ưu Tiên:")
                for item in guidelines['priorities']:
                    lines.append(f"- {item}")
        
        return "\n".join(lines)


class GlossaryManager:
    """
    Lớp quản lý bảng thuật ngữ từ glossary.csv.
    
    Glossary chứa các thuật ngữ cần dịch đồng nhất (tên nhân vật, địa danh,
    khái niệm đặc biệt...) với cách dịch chuẩn và ghi chú.
    """
    
    def __init__(self, glossary_path: Path):
        """
        Khởi tạo GlossaryManager và nạp glossary từ file CSV.
        
        Args:
            glossary_path (Path): Đường dẫn đến file glossary.csv
        """
        self.glossary_path = glossary_path
        self.entries = []
        self._load_glossary()
    
    def _load_glossary(self) -> None:
        """Đọc và parse file glossary.csv."""
        try:
            with open(self.glossary_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.entries = list(reader)
            
            logging.info(f"✅ Đã nạp {len(self.entries)} mục từ glossary.")
        
        except Exception as e:
            logging.warning(f"⚠️  Không thể đọc glossary: {e}")
            self.entries = []
    
    def format_for_prompt(self, max_entries: int = 50) -> str:
        """
        Format glossary thành bảng thuật ngữ để chèn vào prompt.
        
        Chỉ lấy các mục có độ ưu tiên cao (High, Medium) và giới hạn số lượng
        để tránh prompt quá dài.
        
        Args:
            max_entries (int): Số lượng mục tối đa để đưa vào prompt
            
        Returns:
            str: Bảng thuật ngữ đã format
        """
        if not self.entries:
            return "Không có bảng thuật ngữ."
        
        lines = []
        lines.append("## BẢNG THUẬT NGỮ CHUẨN")
        lines.append("")
        lines.append("| Loại | Tiếng Trung | Phiên Âm | Bản Dịch | Biến Thể | Cách Dịch | Ghi Chú |")
        lines.append("|------|-------------|----------|----------|----------|-----------|---------|")
        
        # Lọc và sắp xếp theo độ ưu tiên
        priority_map = {'High': 1, 'Medium': 2, 'Low': 3}
        sorted_entries = sorted(
            self.entries,
            key=lambda x: priority_map.get(x.get('Priority', 'Low'), 3)
        )
        
        # Chỉ lấy High và Medium
        filtered_entries = [
            e for e in sorted_entries 
            if e.get('Priority') in ['High', 'Medium']
        ][:max_entries]
        
        for entry in filtered_entries:
            category = entry.get('Category', '')
            chinese = entry.get('Chinese', '')
            pinyin = entry.get('Pinyin', '')
            vietnamese = entry.get('Vietnamese', '')
            variants = entry.get('Variants', '')
            method = entry.get('Translation_Method', '')
            notes = entry.get('Notes', '')
            
            lines.append(f"| {category} | {chinese} | {pinyin} | {vietnamese} | {variants} | {method} | {notes} |")
        
        lines.append("")
        lines.append("**LƯU Ý QUAN TRỌNG**: Phải tuân thủ TUYỆT ĐỐI bảng thuật ngữ trên. "
                    "Mọi thuật ngữ xuất hiện trong văn bản gốc PHẢI được dịch chính xác "
                    "theo cột 'Bản Dịch'. Sử dụng 'Biến Thể' khi phù hợp với ngữ cảnh.")
        
        return "\n".join(lines)


class CharacterRelationsManager:
    """
    Lớp quản lý ma trận quan hệ nhân vật từ character_relations.csv.
    
    File này chứa thông tin về cách các nhân vật xưng hô với nhau dựa trên
    mối quan hệ, bối cảnh, và động lực quyền lực.
    """
    
    def __init__(self, relations_path: Path):
        """
        Khởi tạo CharacterRelationsManager và nạp relations từ file CSV.
        
        Args:
            relations_path (Path): Đường dẫn đến file character_relations.csv
        """
        self.relations_path = relations_path
        self.relations = []
        self._load_relations()
    
    def _load_relations(self) -> None:
        """Đọc và parse file character_relations.csv."""
        try:
            with open(self.relations_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.relations = list(reader)
            
            logging.info(f"✅ Đã nạp {len(self.relations)} quan hệ nhân vật.")
        
        except Exception as e:
            logging.warning(f"⚠️  Không thể đọc character relations: {e}")
            self.relations = []
    
    def format_for_prompt(self, max_relations: int = 30) -> str:
        """
        Format ma trận quan hệ thành hướng dẫn xưng hô để chèn vào prompt.
        
        Args:
            max_relations (int): Số lượng quan hệ tối đa để đưa vào prompt
            
        Returns:
            str: Hướng dẫn xưng hô đã format
        """
        if not self.relations:
            return "Không có ma trận quan hệ nhân vật."
        
        lines = []
        lines.append("## HƯỚNG DẪN XƯNG HÔ GIỮA CÁC NHÂN VẬT")
        lines.append("")
        lines.append("Bảng dưới đây quy định cách các nhân vật xưng hô với nhau. "
                    "Khi dịch hội thoại, PHẢI tuân thủ các quy tắc xưng hô này:")
        lines.append("")
        
        # Nhóm theo relationship type để dễ đọc hơn
        grouped_relations = {}
        for relation in self.relations[:max_relations]:
            rel_type = relation.get('Relationship_Type', 'other')
            if rel_type not in grouped_relations:
                grouped_relations[rel_type] = []
            grouped_relations[rel_type].append(relation)
        
        for rel_type, relations in grouped_relations.items():
            lines.append(f"### {rel_type.replace('_', ' ').title()}")
            lines.append("")
            
            for rel in relations:
                speaker = rel.get('Speaker_ID', '')
                listener = rel.get('Listener_ID', '')
                context = rel.get('Context', '')
                power = rel.get('Power_Dynamic', '')
                emotion = rel.get('Emotional_State', '')
                speaker_pronoun = rel.get('Speaker_Pronoun', '')
                listener_term = rel.get('Listener_Term', '')
                notes = rel.get('Notes', '')
                
                lines.append(f"**{speaker} → {listener}**")
                lines.append(f"- Ngữ cảnh: {context}")
                lines.append(f"- Quyền lực: {power}, Cảm xúc: {emotion}")
                lines.append(f"- Người nói ({speaker}) tự xưng: {speaker_pronoun}")
                lines.append(f"- Người nói gọi {listener}: {listener_term}")
                
                if notes:
                    lines.append(f"- Ghi chú: {notes}")
                lines.append("")
        
        lines.append("**LƯU Ý**: Xưng hô có thể thay đổi tùy theo ngữ cảnh, "
                    "cảm xúc và động lực quyền lực. Ưu tiên sử dụng xưng hô "
                    "phù hợp nhất với tình huống cụ thể trong văn bản.")
        
        return "\n".join(lines)


def load_guidelines_from_instructions_dir() -> str:
    """
    Nạp tất cả các file guidelines từ thư mục prompts/instructions/.
    
    Tìm và nạp các file:
    - style_profile.json
    - glossary.csv
    - character_relations.csv
    
    Returns:
        str: Văn bản chỉ dẫn dịch thuật đã được tổng hợp và format
    """
    instructions_dir = Path('prompts/instructions')
    
    if not instructions_dir.exists():
        logging.info("ℹ️  Không tìm thấy thư mục prompts/instructions/.")
        return "Không có chỉ dẫn dịch thuật đặc biệt. Áp dụng các nguyên tắc dịch thuật chuẩn."
    
    sections = []
    
    # Nạp style profile
    style_file = instructions_dir / 'style_profile.json'
    if style_file.exists():
        try:
            with open(style_file, 'r', encoding='utf-8') as f:
                style_data = json.load(f)
            
            logging.info("✅ Đã nạp style_profile.json từ prompts/instructions/.")
            style_profile = StyleProfile(style_data)
            sections.append(style_profile.format_for_prompt())
        
        except Exception as e:
            logging.warning(f"⚠️  Lỗi khi đọc style_profile.json: {e}")
    
    # Nạp glossary
    glossary_file = instructions_dir / 'glossary.csv'
    if glossary_file.exists():
        glossary = GlossaryManager(glossary_file)
        sections.append(glossary.format_for_prompt())
    
    # Nạp character relations
    relations_file = instructions_dir / 'character_relations.csv'
    if relations_file.exists():
        relations = CharacterRelationsManager(relations_file)
        sections.append(relations.format_for_prompt())
    
    # Nếu không có guidelines nào, trả về thông báo
    if not sections:
        return "Không có chỉ dẫn dịch thuật đặc biệt. Áp dụng các nguyên tắc dịch thuật chuẩn."
    
    # Ghép nối các sections với dòng phân cách
    result = "\n\n" + "="*80 + "\n"
    result += "CHỈ DẪN DỊCH THUẬT CỤ THỂ CHO TÁC PHẨM NÀY"
    result += "\n" + "="*80 + "\n\n"
    result += "\n\n".join(sections)
    result += "\n\n" + "="*80 + "\n"
    
    return result


# Giữ lại các hàm cũ để tương thích ngược (deprecated)
def build_translation_guidelines(project_dir: Path) -> str:
    """
    [DEPRECATED] Hàm cũ tìm guidelines trong thư mục dự án.
    Giờ sử dụng load_guidelines_from_instructions_dir() thay thế.
    
    Args:
        project_dir (Path): Đường dẫn đến thư mục dự án (không còn sử dụng)
        
    Returns:
        str: Văn bản chỉ dẫn dịch thuật
    """
    logging.info("⚠️  build_translation_guidelines() đã lỗi thời. Chuyển sang nạp từ prompts/instructions/.")
    return load_guidelines_from_instructions_dir()
