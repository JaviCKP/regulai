from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('front', '0031_infer_historical_prompt_company')]

    operations = [
        migrations.AddField(model_name='obfuscationconfig', name='backend',
            field=models.CharField(choices=[('local', 'Local detector'), ('http', 'PasteGuard HTTP')],
                default='http', max_length=10)),
        migrations.AlterField(model_name='obfuscationconfig', name='api_url',
            field=models.URLField(blank=True,
                help_text='Base URL del servicio PasteGuard; obligatoria solo para HTTP.')),
    ]
