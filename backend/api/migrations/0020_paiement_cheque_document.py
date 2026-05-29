from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0019_otpcode'),
    ]

    operations = [
        migrations.AddField(
            model_name='paiement',
            name='cheque_document',
            field=models.FileField(blank=True, null=True, upload_to='cheques/%Y/%m/'),
        ),
    ]
