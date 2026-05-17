# High Level Requirement

Allow scripts to describe an image as being created from a Dockerfile which is layered on top of an existing image.

for example
```python
base_image = RemoteImage("ubuntu", "24.04")

layer = ImageLayer(...) # args TBD

derived_image = layer(base_image, ...) # args TBD

# derived_image store the metadata about how the image would be built

# and then it can be build separately
await derived_image.build()
```

`ImageLayer` defines a Layer that can be layered on top of some other image.
`ImageLayer` behaves like a factory that produces a new object (we will call `LayeredImage`).

`ImageLayer` should define a base/default name that the `LayeredImage` will adopt if no override is given to `LayeredImage.build`.

`ImageLayer` should define what build args are avaliable to the image and optionally have default for each arg. This will be useful for check if the build args passed during `LayeredImage.build` is valid: ones without default are not missing, no extra build args that is not defined at `ImageLayer` creation.

```python
class ImageLayer:
    ...

    def __init__(
        self,
        dockerfile: Path,
        name: str,
        tag: str,
        build_arg_defs: dict[str, str | None],
    ) -> None:
        ...
        
    def __call__(
        self,
        base: Image,
        *,
        name: str | None = None,
        tag: str | None = None,
        build_args: dict[str, str] | None = None,
    ) -> LayeredImage:
        ...
```

Since we will want a unifed interface for ensuring an image exists, let's add `ensure_exists` method to `Image` so that no mater which `base: Image` we have, we can call `await base.ensure_exists`
