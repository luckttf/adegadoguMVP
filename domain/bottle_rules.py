"""Regras puras para rendimento de garrafas e doses."""
from math import isfinite

VOLUME_GARRAFA_ML_PADRAO = 900
VOLUME_DOSE_ML_PADRAO = 150
FATOR_PERDA_PADRAO = 0.05  # ajuste legado para preservar o rendimento operacional padrão de 5,7 doses; não é um registro de perda real


def calcular_doses_estimadas(volume_garrafa_ml: int = VOLUME_GARRAFA_ML_PADRAO,
                             volume_dose_ml: int = VOLUME_DOSE_ML_PADRAO,
                             fator_perda: float = FATOR_PERDA_PADRAO) -> tuple[float, float]:
    """Retorna doses teóricas e rendimento operacional estimado; 5,7 é referência, não perda real registrada."""
    if not isinstance(volume_garrafa_ml, (int, float)) or not isfinite(float(volume_garrafa_ml)) or volume_garrafa_ml <= 0:
        raise ValueError("O volume da garrafa deve ser positivo.")
    if not isinstance(volume_dose_ml, (int, float)) or not isfinite(float(volume_dose_ml)) or volume_dose_ml <= 0:
        raise ValueError("O volume da dose deve ser positivo.")
    if not isinstance(fator_perda, (int, float)) or not isfinite(float(fator_perda)) or not 0 <= fator_perda < 1:
        raise ValueError("O ajuste de rendimento deve estar entre 0% e menos de 100%.")
    teoricas = float(volume_garrafa_ml) / float(volume_dose_ml)
    estimadas = teoricas * (1 - float(fator_perda))
    return round(teoricas, 2), round(estimadas, 2)
