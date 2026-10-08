from myfirstapp.db import get_db

class Image:
    def __init__(self, id, imagelink, caption, author_id, created):
        self.id, self.imagelink, self.caption = id, imagelink, caption
        self.author_id, self.created = author_id, created

    @staticmethod
    def find_by_author(author_id): ...   # SELECT ... WHERE author_id = ?
    @staticmethod
    def find(id): ...                    # returns an Image or None
    @staticmethod
    def create(imagelink, caption, author_id): ...
    @staticmethod
    def delete(id): ...