import rollnw
from PIL import Image
import configparser
import sys


def item_to_image(item: rollnw.Item) -> Image:
    """Converts an item to an icon image"""

    bi_2da = rollnw.kernel.twodas().get("baseitems")
    model_type = bi_2da.get(item.baseitem, "ModelType")

    if model_type == 0:
        simple_icon = item.get_icon_by_part()
        simple_image = Image.frombytes(
            "RGBA", (simple_icon.width(), simple_icon.height()), simple_icon.data())
        return simple_image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    elif model_type == 1:
        layered_icon = item.get_icon_by_part()
        layered_image = Image.frombytes(
            "RGBA", (layered_icon.width(), layered_icon.height()), layered_icon.data())
        return layered_image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    elif model_type == 2:
        bottom = item.get_icon_by_part(rollnw.ItemModelParts.model1)
        bottom_image = Image.frombytes(
            "RGBA", (bottom.width(), bottom.height()), bottom.data())

        middle = item.get_icon_by_part(rollnw.ItemModelParts.model2)
        middle_image = Image.frombytes(
            "RGBA", (middle.width(), middle.height()), middle.data())

        top = item.get_icon_by_part(rollnw.ItemModelParts.model3)
        top_image = Image.frombytes(
            "RGBA", (top.width(), top.height()), top.data())

        bottom_image.paste(middle_image, (0, 0), middle_image)
        bottom_image.paste(top_image, (0, 0), top_image)

        return bottom_image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    elif model_type == 3:
        base_image = None

        parts = [rollnw.ItemModelParts.armor_pelvis,
                 rollnw.ItemModelParts.armor_belt,
                 rollnw.ItemModelParts.armor_torso,
                 rollnw.ItemModelParts.armor_lshoul,
                 rollnw.ItemModelParts.armor_rshoul,
                 rollnw.ItemModelParts.armor_robe]

        for part in parts:
            texture = item.get_icon_by_part(part)
            if texture is not None:
                image = Image.frombytes(
                    "RGBA", (texture.width(), texture.height()), texture.data())
                if base_image is None:
                    base_image = image
                else:
                    base_image.paste(image, (0, 0), image)

        if base_image is not None:
            return base_image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def make_minimap(area: rollnw.Area):
    def chunks(l, n):
        """Cut a slicable object into N length pieces.
        """
        return [l[i:i + n] for i in range(0, len(l), n)]

    scale = 1
    minimum = 32
    texture_map = {}
    config = configparser.ConfigParser()
    textures = []
    texture_size = sys.maxsize

    set_file = rollnw.kernel.resman().demand(area.tileset_resref + ".set")
    config.read_string(set_file.bytes.decode())

    for tile in area.tiles:
        texture_name = config.get(f'TILE{tile.id}', 'ImageMap2D').lower()

        if not texture_name in texture_map:
            texture_map[texture_name] = texture_to_image(texture_name)

        image = texture_map[texture_name]

        # I chose here to scale all the minimap images to the smallest size so if one is 8x8
        # they will all be scaled to 8x8.
        texture_size = min(texture_size, image.width)
        textures.append((image, tile.orientation))

    # Note: The tile list begins in the bottom left corner  so I'm going to reverse so that it
    # starts in the top left and draw down rather than up.
    textures = chunks(textures, area.width)[::-1]

    # minimum minimap tile size 16x16, just so some of the smaller 8x8s are a little larger.
    texture_size = max(minimum, texture_size * scale)

    image = Image.new('RGBA', (area.width * texture_size,
                               area.height * texture_size))

    for h in range(area.height):
        for w in range(area.width):
            im, rot = textures[h][w]
            location = (w * texture_size, h * texture_size)

            if im.size[0] != texture_size:
                im = im.resize((texture_size, texture_size))

            # Note: tile orientation is 0, 1, 2, 3 corresponding to 0, 90, 180, 240, etc
            # degrees of rotation, i,e tile.orientation * 90 == rotation in degrees.
            image.paste(im.rotate(rot*90), location)

    return image


def texture_to_image(resref: str):
    image = rollnw.kernel.resman().texture(resref)
    if image.channels() == 4:
        return Image.frombytes("RGBA", (image.width(), image.height()), image.data())
    else:
        return Image.frombytes("RGB", (image.width(), image.height()), image.data())


__all__ = [
    "item_to_image",
    "make_minimap",
    "texture_to_image",
]
