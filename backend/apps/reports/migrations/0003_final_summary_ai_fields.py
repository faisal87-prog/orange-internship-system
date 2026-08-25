# Generated manually for Final Internship Summary AI fields.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0002_weekly_report_ai_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="finalinternshipsummary",
            name="generated_by_ai",
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name="finalinternshipsummary",
            constraint=models.UniqueConstraint(
                fields=("intern", "program"),
                name="unique_final_summary_intern_program",
            ),
        ),
    ]
