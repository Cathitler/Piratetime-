from PIL import Image
import os

def convert_image(input_path, output_path=None, output_format=None):
    """
    Convert image between JPG and PNG formats
    
    Args:
        input_path: Path to input image file
        output_path: Path to output image file (optional)
        output_format: 'PNG' or 'JPEG' (optional, will auto-detect from output_path)
    """
    # Open the image
    img = Image.open(input_path)
    
    # Determine output format if not specified
    if output_format is None and output_path is not None:
        output_format = output_path.split('.')[-1].upper()
        if output_format == 'JPG':
            output_format = 'JPEG'
    
    # Convert RGBA to RGB for JPEG (JPEG doesn't support transparency)
    if output_format == 'JPEG' and img.mode == 'RGBA':
        # Create a white background
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, (0, 0), img)
        img = background
    elif output_format == 'JPEG' and img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Save the image
    if output_path:
        img.save(output_path, format=output_format)
    else:
        # Generate output path
        base_name = os.path.splitext(input_path)[0]
        ext = '.png' if output_format == 'PNG' else '.jpg'
        output_path = base_name + ext
        img.save(output_path, format=output_format)
    
    print(f"Image converted: {input_path} -> {output_path}")
    return output_path

def convert_jpg_to_png(input_path, output_path=None):
    """Convert JPG to PNG"""
    return convert_image(input_path, output_path, 'PNG')

def convert_png_to_jpg(input_path, output_path=None, quality=95):
    """Convert PNG to JPG"""
    img = Image.open(input_path)
    
    # Convert to RGB if necessary
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, (0, 0), img)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    if output_path is None:
        base_name = os.path.splitext(input_path)[0]
        output_path = base_name + '.jpg'
    
    img.save(output_path, 'JPEG', quality=quality)
    print(f"Image converted: {input_path} -> {output_path}")
    return output_path

# Example usage
if __name__ == "__main__":
    # Convert JPG to PNG
    convert_jpg_to_png('image.jpg', 'image.png')
    
    # Convert PNG to JPG
    convert_png_to_jpg('image.png', 'image.jpg', quality=90)
    
    # Convert with auto-detection
    convert_image('image.jpg', 'output.png')
    convert_image('image.png', 'output.jpg')