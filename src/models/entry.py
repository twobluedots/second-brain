from pydantic import BaseModel
from typing import Optional, List


class Entry(BaseModel):
    content: Optional[str] = None
    content_type: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    file_path: Optional[str] = None
