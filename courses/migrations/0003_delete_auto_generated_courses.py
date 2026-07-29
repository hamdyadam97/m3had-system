from django.db import migrations


def delete_auto_generated_courses(apps, schema_editor):
    """يحذف الدورات اللي اتعملت تلقائياً باسم AUTO-xxxxxxxx من كود قديم كان
    بينشئ دورة جديدة لأي اسم مش موجود بدل ما يرفض الصف (تم إلغاء السلوك ده).
    غالباً أسماء أشخاص انحطت بالغلط في عمود الدورة أثناء استيراد Excel.
    """
    Course = apps.get_model('courses', 'Course')
    Course.objects.filter(code__startswith='AUTO-').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0002_alter_course_course_type'),
        ('transactions', '0013_alter_expense_category'),
    ]

    operations = [
        migrations.RunPython(delete_auto_generated_courses, migrations.RunPython.noop),
    ]
