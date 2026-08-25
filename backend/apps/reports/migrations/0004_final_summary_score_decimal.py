# Generated manually for Final Summary automatic score (decimal average).

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0003_final_summary_ai_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="finalinternshipsummary",
            name="final_score",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=5,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
    ]
