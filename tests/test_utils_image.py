from arclight.utils import image
import rollnw


def test_item_to_image() -> None:
    rollnw.kernel.start()
    item = rollnw.kernel.objects().item("x2_it_drowcl001")
    assert item
    img = image.item_to_image(item)
    assert img


def test_make_minimap() -> None:
    rollnw.kernel.start()
    mod = rollnw.kernel.load_module("tests/test_data/DockerDemo.mod")
    img = image.make_minimap(mod.get_area(0))
    assert img
