from repositories.prediction_repository import PredictionRepository


class PredictionService:

    @staticmethod
    def save_prediction(
        db,
        news,
        ai_result
    ):

        return PredictionRepository.save_prediction(
            db,
            news,
            ai_result
        )

    @staticmethod
    def get_today_predictions(db):

        return PredictionRepository.get_today_predictions(db)