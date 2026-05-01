import os
import io
import time
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.utils.file_utils import FileProcessor

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_LIB_INSTALLED = True
except ImportError:
    ARABIC_LIB_INSTALLED = False
    print("⚠️ تحذير: مكتبات اللغة العربية غير مثبتة.")

def process_text_to_pdf(text, file_name, user_id):
    output = FileProcessor.build_output_path(user_id, file_name)
    
    c = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    margin = 40
    line_height = 20
    y_position = height - margin
    
    # إعداد الخط
    font_name = "Helvetica"
    try:
        # Check specific path in assets/fonts for Bold font
        font_path = os.path.join(AdvancedConfig.BASE_DIR, "assets", "fonts", "arialbd.ttf")
        
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Arabic', font_path))
            font_name = 'Arabic'
        else:
            print(f"⚠️ تحذير: ملف الخط غير موجود في المسار: {font_path}")
    except Exception as e: 
        print(f"⚠️ خطأ في تحميل الخط: {e}")
        pass
    
    c.setFont(font_name, 12)
    
    # تقسيم النص إلى أسطر
    lines = []
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            lines.append("")  # سطر فارغ
            continue
            
        # معالجة النص العربي
        if ARABIC_LIB_INSTALLED and font_name == 'Arabic':
            try:
                paragraph = get_display(arabic_reshaper.reshape(paragraph))
            except:
                pass
        
        # تقسيم الفقرة إلى أسطول تناسب الصفحة
        words = paragraph.split()
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            line_width = c.stringWidth(test_line, font_name, 12)
            
            if line_width <= (width - 2 * margin):
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
    
    # كتابة النص على الصفحات
    page_num = 1
    for line in lines:
        if y_position < margin + line_height:
            # صفحة جديدة
            c.showPage()
            c.setFont(font_name, 12)
            y_position = height - margin
            page_num += 1
        
        if line:  # إذا كان السطر ليس فارغاً
            if font_name == 'Arabic':
                 c.drawRightString(width - margin, y_position, line)
            else:
                 c.drawString(margin, y_position, line)
        
        y_position -= line_height
    
    c.save()
    return output

def process_file_info(file_path):
    name_no_ext = os.path.splitext(os.path.basename(file_path))[0]
    ext = os.path.splitext(file_path)[1].replace('.', '').upper()
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    pages = "غير معروف"
    encrypted = "لا"
    watermark = "لا"
    creator = "غير معروف"
    
    if ext == 'PDF':
        try:
            reader = PdfReader(file_path)
            if reader.is_encrypted:
                encrypted = "نعم"
                pages = "مخفي (مشفر)"
            else:
                pages = len(reader.pages)
                
            # استخراج معلومات البرنامج المستخدم
            if reader.metadata:
                if '/Creator' in reader.metadata:
                    creator = reader.metadata['/Creator']
                elif '/Producer' in reader.metadata:
                    creator = reader.metadata['/Producer']
        except: 
            pass

    info = (
        f"📊 <b>معلومات الملف</b>\n\n"
        f"🏷 <b>الاسم:</b> {name_no_ext}\n"
        f"📁 <b>النوع:</b> {ext}\n"
        f"📄 <b>الصفحات:</b> {pages}\n"
        f"💾 <b>الحجم:</b> {size_mb:.2f} ميجابايت\n"
        f"🔒 <b>التشفير:</b> {encrypted}\n"
        f"💧 <b>علامة مائية:</b> {watermark}\n"
        f"🖋️ <b>برنامج الكتابة:</b> {creator}"
    )
    return info

def process_merge_pdf(paths, name, uid):
    writer = PdfWriter()
    for p in paths: 
        writer.append(p)
    out = FileProcessor.build_output_path(uid, name)
    writer.write(out)
    return out

def process_encrypt_pdf(path, pwd, uid):
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(pwd)
    base = os.path.splitext(os.path.basename(path))[0]
    out = FileProcessor.build_output_path(uid, f"{base}_محمي")
    with open(out, 'wb') as f:
        writer.write(f)
    return out

def process_watermark(path, text, uid):
    try:
        reader = PdfReader(path)
        writer = PdfWriter()

        for page in reader.pages:
            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=page.mediabox)

            c.setFont("Helvetica", 40)
            c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.3)
            c.rotate(45)

            width = float(page.mediabox.width)
            height = float(page.mediabox.height)

            c.drawString(width / 2 - 100, height / 2, text)

            c.save()

            packet.seek(0)
            watermark_page = PdfReader(packet)
            page.merge_page(watermark_page.pages[0])

            writer.add_page(page)

        base = os.path.splitext(os.path.basename(path))[0]
        out = FileProcessor.build_output_path(uid, f"{base}_علامة_مائية")
        with open(out, 'wb') as f:
            writer.write(f)
        return out
    except Exception as e:
        raise Exception(f"خطأ في إضافة العلامة المائية: {str(e)}")

def process_compress_pdf(path, uid):
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for page in writer.pages:
        page.compress_content_streams()
    base = os.path.splitext(os.path.basename(path))[0]
    out = FileProcessor.build_output_path(uid, f"{base}_مضغوط")
    with open(out, 'wb') as f:
        writer.write(f)
    return out

def process_split_pdf(path, pages, name, uid):
    reader = PdfReader(path)
    writer = PdfWriter()
    total_pages = len(reader.pages)

    pages_clean = pages.replace(" ", "")
    if '-' in pages_clean:
        start_str, end_str = pages_clean.split('-', 1)
        if not start_str.isdigit() or not end_str.isdigit():
            raise ValueError("صيغة نطاق الصفحات غير صحيحة")
        start, end = int(start_str), int(end_str)
    else:
        if not pages_clean.isdigit():
            raise ValueError("صيغة نطاق الصفحات غير صحيحة")
        start = end = int(pages_clean)

    if start < 1 or end < 1:
        raise ValueError("رقم الصفحة يجب أن يكون أكبر من 0")
    if start > end:
        start, end = end, start
    if start > total_pages:
        raise ValueError("رقم صفحة البداية أكبر من عدد صفحات الملف")
    if end > total_pages:
        end = total_pages

    for i in range(start - 1, end):
        writer.add_page(reader.pages[i])

    out = FileProcessor.build_output_path(uid, name)
    with open(out, 'wb') as f:
        writer.write(f)
    return out

def process_rotate_pdf(path, angle, uid):
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(angle)
        writer.add_page(page)
    base = os.path.splitext(os.path.basename(path))[0]
    out = FileProcessor.build_output_path(uid, f"{base}_تدوير_{angle}")
    with open(out, 'wb') as f:
        writer.write(f)
    return out

