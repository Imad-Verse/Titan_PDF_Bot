import sys
import os
import time
import sqlite3
import telebot
from telebot import types
from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.loader import bot
from titan_pdf_bot.core.database import db
from titan_pdf_bot.core.logger import logger
from titan_pdf_bot.core.session import session_manager
from titan_pdf_bot.utils.ui_utils import UIManager
from titan_pdf_bot.utils.helpers import is_maintenance_mode, set_maintenance_mode, format_duration

@bot.message_handler(func=lambda m: m.text == "⚙️ إعدادات المدير")
def handle_admin_settings_button(message):
    user_id = message.from_user.id
    if user_id not in AdvancedConfig.ADMINS:
        bot.reply_to(message, "🚫 <b>غير مصرح لك بالوصول لهذه الصفحة</b>", 
                    parse_mode='HTML', reply_markup=UIManager.create_error_buttons())
        return
    bot.send_message(message.chat.id, "⚙️ <b>إعدادات المدير</b>\nاختر الإجراء المطلوب:", 
                    reply_markup=UIManager.create_admin_settings_menu(), parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == "admin_settings")
def handle_admin_settings_callback(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    if user_id not in AdvancedConfig.ADMINS:
        bot.send_message(
            call.message.chat.id,
            "🚫 <b>غير مصرح لك بالوصول لهذه الصفحة</b>",
            parse_mode='HTML',
            reply_markup=UIManager.create_error_buttons()
        )
        return

    bot.send_message(
        call.message.chat.id,
        "⚙️ <b>إعدادات المدير</b>\nاختر الإجراء المطلوب:",
        reply_markup=UIManager.create_admin_settings_menu(),
        parse_mode='HTML'
    )


@bot.message_handler(func=lambda m: m.text in [
    "📊 إحصائيات النظام", "🚫 إدارة الحظر", "📢 الإذاعة للمستخدمين",
    "🔄 إعادة تشغيل البوت", "📦 تحديث المكتبات", "💾 نسخ قاعدة البيانات",
    "🔧 وضع الصيانة"
])
def handle_admin_settings(message):
    user_id = message.from_user.id
    if user_id not in AdvancedConfig.ADMINS:
        bot.reply_to(message, "🚫 <b>غير مصرح لك بالوصول لهذه الصفحة</b>", 
                    parse_mode='HTML', reply_markup=UIManager.create_error_buttons())
        return
    
    text = message.text
    
    if text == "📊 إحصائيات النظام":
        stats = db.get_system_stats()
        sys_info = f"""
<b>📊 إحصائيات النظام الشاملة</b>

<b>👥 المستخدمون:</b>
• إجمالي المستخدمين: <code>{stats['total_users']}</code>
• المستخدمون النشطون اليوم: <code>{stats['active_users']}</code>

<b>⚙️ العمليات:</b>
• إجمالي العمليات: <code>{stats['total_operations']}</code>
• عمليات اليوم: <code>{stats['today_operations']}</code>

<b>💾 النظام:</b>
• الملفات المؤقتة: <code>{len(os.listdir(AdvancedConfig.TEMP_DIR))}</code>
• حجم قاعدة البيانات: <code>{os.path.getsize(AdvancedConfig.DB_FILE) // 1024}</code> كيلوبايت
• وقت التشغيل: منذ <code>{format_duration(time.time() - AdvancedConfig.START_TIME)}</code>
"""
        bot.reply_to(message, sys_info, parse_mode='HTML')
    
    elif text == "🚫 إدارة الحظر":
        msg = bot.reply_to(message, "🆔 <b>أرسل معرف المستخدم (User ID) للمستخدم المراد حظره/فك حظره:</b>\n\nيمكنك إلغاء العملية بالضغط على زر 'إلغاء وعودة' أدناه.", 
                          parse_mode='HTML', reply_markup=UIManager.create_cancel_only_keyboard())
        bot.register_next_step_handler(msg, process_admin_ban_step)
    
    elif text == "📢 الإذاعة للمستخدمين":
        session_manager.create_session(user_id, 'broadcasting')
        msg = bot.reply_to(message, "📢 <b>أرسل الرسالة التي تود إذاعتها لجميع المستخدمين:</b>\n\nيمكن أن تكون نصاً، صورة، أو ملفاً.\nللإلغاء، اضغط 'إلغاء وعودة'.", 
                          parse_mode='HTML', reply_markup=UIManager.create_cancel_only_keyboard())
        bot.register_next_step_handler(msg, process_admin_broadcast_step)
    
    elif text == "🔄 إعادة تشغيل البوت":
        bot.reply_to(message, "🔄 <b>جاري إعادة تشغيل النظام...</b>\nسيتم استئناف العمل خلال 10 ثوانٍ.", parse_mode='HTML')
        logger.log('info', "إعادة تشغيل النظام مطلوبة من المدير")
        
        with open(AdvancedConfig.RESTART_LOG_FILE, "w") as f:
            f.write(str(message.chat.id))
        
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except: pass

        try:
            bot.stop_polling()
        except: pass

        try:
            logger.logger.handlers = []
        except: pass

        time.sleep(1) # Reduced from 5
        
        python = sys.executable
        os.execl(python, python, *sys.argv)
    
    elif text == "📦 تحديث المكتبات":
        bot.reply_to(
            message,
            "ℹ️ <b>تم تعطيل التحديث المباشر من داخل البوت حفاظاً على الاستقرار.</b>\n\n"
            "حدّث المكتبات من بيئة التشغيل يدويًا ثم أعد تشغيل البوت:\n"
            "<code>pip install --upgrade -r requirements.txt</code>",
            parse_mode='HTML'
        )
    
    elif text == "💾 نسخ قاعدة البيانات":
        try:
            backup_path = db.backup_database()
            with open(backup_path, 'rb') as f:
                bot.send_document(message.chat.id, f, 
                                caption=f"💾 <b>نسخة احتياطية:</b> <code>{os.path.basename(backup_path)}</code>", 
                                parse_mode='HTML')
        except Exception as e:
            bot.reply_to(message, f"❌ <b>خطأ في إنشاء النسخة الاحتياطية:</b>\n<code>{str(e)}</code>", 
                        parse_mode='HTML', reply_markup=UIManager.create_error_buttons())
    
    elif text == "🔧 وضع الصيانة":
        if is_maintenance_mode():
            set_maintenance_mode(False)
            bot.reply_to(message, "🟢 <b>تم إيقاف وضع الصيانة.</b>\nالبوت الآن متاح لجميع المستخدمين.", parse_mode='HTML')
        else:
            set_maintenance_mode(True)
            bot.reply_to(message, "🔴 <b>تم تفعيل وضع الصيانة.</b>\nفقط المديرون يمكنهم استخدام البوت الآن.", parse_mode='HTML')

def process_admin_ban_step(message):
    if message.text == "🔙 إلغاء وعودة":
        bot.send_message(message.chat.id, "✅ <b>تم إلغاء العملية.</b>", 
                        reply_markup=UIManager.create_admin_settings_menu(), parse_mode='HTML')
        return
    
    try:
        target_id = message.text.strip()
        new_status = db.toggle_block_user(target_id)
        
        if new_status is None:
            bot.reply_to(message, "❌ <b>لم يتم العثور على مستخدم بهذا المعرف.</b>", 
                        parse_mode='HTML', reply_markup=UIManager.create_error_buttons())
        elif new_status == 1:
            bot.reply_to(message, f"🚫 <b>تم حظرك المستخدم {target_id} بنجاح.</b>", 
                        parse_mode='HTML', reply_markup=UIManager.create_admin_settings_menu())
        else:
            bot.reply_to(message, f"✅ <b>تم فك حظر المستخدم {target_id} بنجاح.</b>", 
                        parse_mode='HTML', reply_markup=UIManager.create_admin_settings_menu())
            
    except Exception as e:
        bot.reply_to(message, f"❌ <b>حدث خطأ:</b>\n<code>{str(e)}</code>", 
                    parse_mode='HTML', reply_markup=UIManager.create_error_buttons())

def perform_broadcast(message):
    try:
        with sqlite3.connect(AdvancedConfig.DB_FILE) as conn:
            ids = [r[0] for r in conn.execute('SELECT user_id FROM users WHERE is_blocked=0').fetchall()]
    except Exception:
        ids = []

    if not ids:
        bot.reply_to(message, "❌ <b>لا يوجد مستخدمين لاستلام الإذاعة.</b>", parse_mode='HTML')
        return

    suc, fail = 0, 0
    st = bot.send_message(message.chat.id, "📢 جارٍ إرسال الإذاعة للمستخدمين...")
    markup = UIManager.create_broadcast_markup()

    if message.content_type == 'text':
        msg_text = f'''📢 <b>رسالة جديدة من الإدارة:</b>\n\n"{message.text}"\n\n🤖 Titan PDF Bot | @TitanPDFBot'''
        for uid in ids:
            try:
                bot.send_message(int(uid), msg_text, parse_mode="HTML", reply_markup=markup)
                suc += 1
                time.sleep(0.05)
            except telebot.apihelper.ApiTelegramException as e:
                if e.error_code in [403, 400]:
                    db.delete_user(uid)
                fail += 1
            except Exception:
                fail += 1
    else:
        for uid in ids:
            try:
                bot.copy_message(int(uid), message.chat.id, message.message_id, reply_markup=markup)
                suc += 1
                time.sleep(0.05)
            except telebot.apihelper.ApiTelegramException as e:
                if e.error_code in [403, 400]:
                    db.delete_user(uid)
                fail += 1
            except Exception:
                fail += 1

    bot.edit_message_text(
        f"✅ <b>تم الإرسال!</b>\n\n✅ <b>نجح:</b> {suc}\n❌ <b>فشل (تم الحظر):</b> {fail}",
        message.chat.id, st.message_id, parse_mode='HTML'
    )

def process_admin_broadcast_step(message):
    if message.text and message.text == "🔙 إلغاء وعودة":
        session_manager.clear_session(message.from_user.id)
        bot.send_message(
            message.chat.id, "✅ <b>تم إلغاء العملية.</b>",
            reply_markup=UIManager.create_admin_settings_menu(), parse_mode='HTML'
        )
        return

    perform_broadcast(message)
    session_manager.clear_session(message.from_user.id)

