import os
import re
import time
from titan_pdf_bot.core.config import AdvancedConfig

try:
    import docx
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False
    print("تحذير: python-docx غير مثبت. لن يتم دعم ملفات Word في الوقت الحالي.")


_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')


class FileProcessor:
    @staticmethod
    def sanitize_filename(name, default_name="file"):
        if not name:
            return default_name
        name = os.path.basename(name)
        name = _INVALID_CHARS.sub('_', name).strip()
        name = name.rstrip('. ')
        return name or default_name

    @staticmethod
    def make_unique_path(directory, filename):
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base}_{counter}{ext}")
            counter += 1
        return candidate

    @staticmethod
    def build_output_path(user_id, file_name, default_prefix="output"):
        safe_name = FileProcessor.sanitize_filename(file_name or default_prefix, default_prefix)
        if not safe_name.lower().endswith('.pdf'):
            safe_name += '.pdf'
        user_dir = FileProcessor.get_user_directory(user_id)
        return FileProcessor.make_unique_path(user_dir, safe_name)

    @staticmethod
    def validate_file(file_size, file_name, mode=None):
        if file_size > AdvancedConfig.MAX_DOWNLOAD_SIZE:
            limit_mb = AdvancedConfig.MAX_DOWNLOAD_SIZE / 1024 / 1024
            raise ValueError(
                f"⚠️ <b>حجم الملف كبير جداً!</b>\n\n"
                f"حجم الملف المرسل ({file_size / 1024 / 1024:.1f} ميجابايت) يتجاوز الحد المسموح به في تيليجرام ({limit_mb} ميجابايت).\n\n"
                f"💡 <b>حلول مقترحة:</b>\n"
                f"• قم بضغط الملف قبل إرساله.\n"
                f"• إذا كان الملف يحتوي على صور، حاول إرسالها بجودة أقل."
            )

        _, ext = os.path.splitext(file_name.lower())

        if mode == 'img_to_pdf':
            if ext not in ['.jpg', '.jpeg', '.png']:
                raise ValueError("⚠️ نوع الملف غير مدعوم، يرجى إرسال صور (JPG, JPEG, PNG)")
        elif mode in ['pdf_to_img', 'merge_pdf', 'split_pdf', 'encrypt_pdf', 'compress_pdf', 'watermark', 'rotate_pdf']:
            if ext != '.pdf':
                raise ValueError("⚠️ نوع الملف غير مدعوم، يرجى إرسال ملف PDF فقط")
        elif mode == 'text_to_pdf':
            if ext not in ['.txt', '.doc', '.docx'] and ext != '':
                raise ValueError("⚠️ نوع الملف غير مدعوم، يقبل فقط TXT, DOC, DOCX")
        else:
            if ext not in AdvancedConfig.ALLOWED_EXTENSIONS:
                raise ValueError(
                    f"⚠️ صيغة {ext} غير مدعومة. الصيغ المسموحة: {', '.join(AdvancedConfig.ALLOWED_EXTENSIONS)}"
                )

        return True

    @staticmethod
    def get_user_directory(user_id):
        user_dir = os.path.join(AdvancedConfig.TEMP_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    @staticmethod
    def save_file(user_id, file_content, file_name):
        user_dir = FileProcessor.get_user_directory(user_id)
        safe_name = FileProcessor.sanitize_filename(file_name, default_name=f"file_{int(time.time())}")
        file_path = FileProcessor.make_unique_path(user_dir, safe_name)
        with open(file_path, 'wb') as f:
            f.write(file_content)
        return file_path

    @staticmethod
    def save_file_stream(user_id, response_stream, file_name):
        """حفظ ملف من استجابة تدفق (Stream) لتقليل استهلاك الرام"""
        user_dir = FileProcessor.get_user_directory(user_id)
        safe_name = FileProcessor.sanitize_filename(file_name, default_name=f"file_{int(time.time())}")
        file_path = FileProcessor.make_unique_path(user_dir, safe_name)
        
        with open(file_path, 'wb') as f:
            for chunk in response_stream.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return file_path

    @staticmethod
    def extract_text_from_file(file_path):
        '''استخراج النص من الملفات المدعومة'''
        _, ext = os.path.splitext(file_path.lower())

        if ext == '.txt':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()

        elif ext == '.docx' and DOCX_SUPPORT:
            try:
                doc = docx.Document(file_path)
                text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
                return text
            except Exception as e:
                raise Exception(f"خطأ في قراءة ملف DOCX: {str(e)}")

        elif ext == '.doc':
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                    text = content.decode('utf-8', errors='ignore')
                    text = ''.join(char for char in text if char.isprintable() or char in '\n\r\t')
                    return text
            except Exception as e:
                raise Exception(f"خطأ في قراءة ملف DOC: {str(e)}")

        return ""
