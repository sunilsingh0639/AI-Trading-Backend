from repositories.company_repository import CompanyRepository


class CompanyService:

    @staticmethod
    def save_company(db, company):

        return CompanyRepository.save(
            db,
            company
        )