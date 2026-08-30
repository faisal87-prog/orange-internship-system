# Generated manually for Final Summary introduction/training AI fields.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0004_final_summary_score_decimal"),
    ]

    operations = [
        migrations.AddField(
            model_name="finalinternshipsummary",
            name="internship_introduction",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="finalinternshipsummary",
            name="training_summary",
            field=models.TextField(blank=True),
        ),
    ]
