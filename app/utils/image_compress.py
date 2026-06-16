from PIL import Image
import io

def resize_image(image_path, max_size=(512, 512)):
    with Image.open(image_path) as image:
        image.thumbnail(max_size, Image.LANCZOS)
        img_io = io.BytesIO()
        image.save(img_io, format='JPEG', quality=85)
        img_io.seek(0)
        return img_io