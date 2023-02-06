from typing import Optional, cast

import pyarrow as pa
import somacore
from somacore import options

from . import util
from .common_nd_array import NDArray
from .exception import SOMAError
from .types import NTuple
from .util import dense_indices_to_shape

_UNBATCHED = options.BatchSize()


class DenseNDArray(NDArray, somacore.DenseNDArray):
    """
    Represents ``X`` and others.

    [lifecycle: experimental]
    """

    @property
    def shape(self) -> NTuple:
        """
        Return length of each dimension, always a list of length ``ndim``
        """
        return cast(NTuple, self._handle.schema.domain.shape)

    def reshape(self, shape: NTuple) -> None:
        """
        Unsupported operation for this object type.

        [lifecycle: experimental]
        """
        raise NotImplementedError("reshape operation not implemented.")

    # Inherited from somacore
    # * ndim accessor
    # * is_sparse: Final = False

    def read(
        self,
        coords: options.DenseNDCoords,
        *,
        result_order: options.ResultOrderStr = somacore.ResultOrder.ROW_MAJOR,
        batch_size: options.BatchSize = _UNBATCHED,
        partitions: Optional[options.ReadPartitions] = None,
        platform_config: Optional[options.PlatformConfig] = None,
    ) -> pa.Tensor:
        """
        Read a user-defined dense slice of the array and return as an Arrow ``Tensor``.
        Coordinates must specify a contiguous subarray, and the number of coordinates
        must be less than or equal to the number of dimensions. For example, if the array
        is 10 by 20, then some acceptable values of ``coords`` include ``(3, 4)``,
        ``(slice(5, 10),)``, and ``(slice(5, 10), slice(6, 12))``. Slice indices are
        doubly inclusive.

        [lifecycle: experimental]
        """
        del batch_size, partitions, platform_config  # Currently unused.
        self._check_open_read()
        result_order = somacore.ResultOrder(result_order)

        arr = self._handle.reader
        target_shape = dense_indices_to_shape(coords, arr.shape, result_order)
        schema = arr.schema
        ned = arr.nonempty_domain()

        sr = self._soma_reader(result_order=result_order.value)

        if coords is not None:
            if not isinstance(coords, (list, tuple)):
                raise TypeError(
                    f"coords type {type(coords)} unsupported; expected list or tuple"
                )
            if len(coords) < 1 or len(coords) > schema.domain.ndim:
                raise ValueError(
                    f"coords {coords} must have length between 1 and ndim ({schema.domain.ndim}); got {len(coords)}"
                )

            for i, coord in enumerate(coords):
                dim_name = schema.domain.dim(i).name
                if coord is None:
                    pass  # No constraint; select all in this dimension
                elif isinstance(coord, int):
                    sr.set_dim_points(dim_name, [coord])
                elif isinstance(coord, slice):
                    lo_hi = util.slice_to_range(coord, ned[i]) if ned else None
                    if lo_hi is not None:
                        lo, hi = lo_hi
                        if lo < 0 or hi < 0:
                            raise ValueError(
                                f"slice start and stop may not be negative; got ({lo}, {hi})"
                            )
                        if lo > hi:
                            raise ValueError(
                                f"slice start must be <= slice stop; got ({lo}, {hi})"
                            )
                        sr.set_dim_ranges(dim_name, [lo_hi])
                    # Else, no constraint in this slot. This is `slice(None)` which is like
                    # Python indexing syntax `[:]`.
                else:
                    raise TypeError(f"coord type {type(coord)} at slot {i} unsupported")

        sr.submit()

        arrow_tables = []
        while True:
            arrow_table_piece = sr.read_next()
            if not arrow_table_piece:
                break
            arrow_tables.append(arrow_table_piece)

        # For dense arrays there is no zero-output case: attempting to make a test case
        # to do that, say by indexing a 10x20 array by positions 888 and 999, results
        # in read-time errors of the form
        #
        # [TileDB::Subarray] Error: Cannot add range to dimension 'soma_dim_0'; Range [888, 888] is
        # out of domain bounds [0, 9]
        if not arrow_tables:
            raise SOMAError(
                "internal error: at least one table-piece should have been returned"
            )

        arrow_table = pa.concat_tables(arrow_tables)
        return pa.Tensor.from_numpy(
            arrow_table.column("soma_data").to_numpy().reshape(target_shape)
        )

    def write(
        self,
        coords: options.DenseNDCoords,
        values: pa.Tensor,
        *,
        platform_config: Optional[options.PlatformConfig] = None,
    ) -> None:
        """
        Write subarray, defined by ``coords`` and ``values``. Will overwrite existing
        values in the array.

        [lifecycle: experimental]

        Parameters
        ----------
        coords - per-dimension tuple of scalar or slice
            Define the bounds of the subarray to be written.

        values - pyarrow.Tensor
            Define the values to be written to the subarray.  Must have same shape
            as defind by ``coords``, and the type must match the DenseNDArray.
        """
        util.check_type("values", values, (pa.Tensor,))

        del platform_config  # Currently unused.
        self._handle.writer[coords] = values.to_numpy()
