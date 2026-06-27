from repositories.prediction_repository import PredictionRepository


class PredictionService:

    @staticmethod
    def get_today_predictions(db):

        return PredictionRepository.get_today_predictions(db)