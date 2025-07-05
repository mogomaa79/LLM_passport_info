from pydantic import BaseModel, Field
from typing import Any, Dict

class CertainField(str):
    """A string field that includes certainty information."""
    
    def __new__(cls, value: str = "", certainty: bool = False):
        # Create the string instance
        instance = str.__new__(cls, value)
        # Add the certainty attribute
        instance.certainty = certainty
        return instance
    
    def __init__(self, value: str = "", certainty: bool = False):
        # Note: str.__init__ doesn't need to be called explicitly
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "value": str(self),
            "certainty": self.certainty
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CertainField':
        """Create from dictionary."""
        return cls(data.get("value", ""), data.get("certainty", False))
    
    def __str__(self) -> str:
        return super().__str__()
    
    def __repr__(self) -> str:
        return f"CertainField('{super().__str__()}', certainty={self.certainty})"

class PassportExtraction(BaseModel):
    """Simple passport information extracted from an image using the Simple prompt."""
    number: CertainField = Field(default_factory=lambda: CertainField("", False))
    country: CertainField = Field(default_factory=lambda: CertainField("", False))
    name: CertainField = Field(default_factory=lambda: CertainField("", False))
    surname: CertainField = Field(default_factory=lambda: CertainField("", False))
    middle_name: CertainField = Field(default_factory=lambda: CertainField("", False), alias="middle name")
    gender: CertainField = Field(default_factory=lambda: CertainField("", False))
    place_of_birth: CertainField = Field(default_factory=lambda: CertainField("", False), alias="place of birth")
    birth_date: CertainField = Field(default_factory=lambda: CertainField("", False), alias="birth date")
    issue_date: CertainField = Field(default_factory=lambda: CertainField("", False), alias="issue date")
    expiry_date: CertainField = Field(default_factory=lambda: CertainField("", False), alias="expiry date")
    mother_name: CertainField = Field(default_factory=lambda: CertainField("", False), alias="mother name")
    father_name: CertainField = Field(default_factory=lambda: CertainField("", False), alias="father name")
    spouse_name: CertainField = Field(default_factory=lambda: CertainField("", False), alias="spouse name")
    place_of_issue: CertainField = Field(default_factory=lambda: CertainField("", False), alias="place of issue")
    country_of_issue: CertainField = Field(default_factory=lambda: CertainField("", False), alias="country of issue")
    mrzLine1: CertainField = Field(default_factory=lambda: CertainField("", False))
    mrzLine2: CertainField = Field(default_factory=lambda: CertainField("", False))
    
    class Config:
        # Allow arbitrary types for CertainField
        arbitrary_types_allowed = True
        
    def to_dict_with_certainty(self) -> Dict[str, Dict[str, Any]]:
        """Convert to dictionary with certainty information."""
        result = {}
        for field_name, field_value in self.model_dump().items():
            if isinstance(field_value, CertainField):
                result[field_name] = field_value.to_dict()
            else:
                # Handle case where field might be a regular string
                result[field_name] = {
                    "value": str(field_value),
                    "certainty": False
                }
        return result 