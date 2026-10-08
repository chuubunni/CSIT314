
# controller/portfolio_controller.py
class PortfolioController:
    IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}

    def upload_image(self, fileobj, caption, user_id, upload_folder):
        # validate extension -> raise ValueError("Wrong file extension!")
        # save file with uuid name -> Image.create(...)
        return 

    def delete_image(self, image_id, user_id, upload_folder):
        # Image.find -> raise NotFoundError / PermissionError
        # Image.delete, then remove the file from disk
        return 