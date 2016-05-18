import os

def image_to_binary(img_path):
    """
        Returns contents of the given image in binary stream.
    """

    if img_path is None or not os.path.exists(img_path):
        return None

    with open(img_path, 'rb') as image_file:
        return image_file.read()
