from pydantic import BaseModel, Field

class PassportExtraction(BaseModel):
    """Detailed passport information extracted from an image."""
    original_number: str = Field(alias="original number")
    number: str
    original_country: str = Field(alias="original country")
    country: str
    name: str
    surname: str
    middle_name: str = Field(alias="middle name")
    original_gender: str = Field(alias="original gender")
    gender: str
    place_of_birth: str = Field(alias="place of birth")
    original_birth_date: str = Field(alias="original birth date")
    birth_date: str = Field(alias="birth date")
    issue_date: str = Field(alias="issue date")
    original_expiry_date: str = Field(alias="original expiry date")
    expiry_date: str = Field(alias="expiry date")
    mother_name: str = Field(alias="mother name")
    father_name: str = Field(alias="father name")
    place_of_issue: str = Field(alias="place of issue")
    country_of_issue: str = Field(alias="country of issue")
    mrzLine1: str
    mrzLine2: str
    mrzPassportNumber: str
    mrzDateOfBirth: str
    mrzDateOfExpiry: str
    mrzSex: str
    mrzSurname: str
    mrzGivenNames: str 