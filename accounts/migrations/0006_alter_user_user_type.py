# Generated manually for Kimi Code CLI

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_user_approval_status_user_id_number_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='user_type',
            field=models.CharField(
                choices=[
                    ('admin', 'مدير النظام'),
                    ('executive_manager', 'مدير تنفيذي'),
                    ('branch_manager', 'مدير فرع'),
                    ('employee', 'موظف'),
                    ('regional_manager', 'مدير إقليمي'),
                    ('accountant', 'محاسب'),
                ],
                default='employee',
                max_length=20,
                verbose_name='نوع المستخدم'
            ),
        ),
    ]
