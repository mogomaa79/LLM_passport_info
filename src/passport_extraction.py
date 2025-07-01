from pydantic import BaseModel, Field

class PassportExtraction(BaseModel):
    """Simple passport information extracted from an image using the Simple prompt."""
    number: str
    country: str
    name: str
    surname: str
    middle_name: str = Field(alias="middle name")
    gender: str
    place_of_birth: str = Field(alias="place of birth")
    birth_date: str = Field(alias="birth date")
    issue_date: str = Field(alias="issue date")
    expiry_date: str = Field(alias="expiry date")
    mother_name: str = Field(alias="mother name")
    father_name: str = Field(alias="father name")
    spouse_name: str = Field(alias="spouse name")
    place_of_issue: str = Field(alias="place of issue")
    country_of_issue: str = Field(alias="country of issue")
    mrzLine1: str
    mrzLine2: str 