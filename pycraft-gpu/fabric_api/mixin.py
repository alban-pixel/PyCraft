"""Fabric Mixin decorator and method injection system."""
import functools
import inspect
from typing import Any, Callable, Dict, Optional, Type


class CallbackInfo:
    """Carries cancellation state and return value for mixin callback injection."""

    def __init__(self, cancellable: bool = False) -> None:
        self.cancellable = cancellable
        self._cancelled: bool = False
        self._return_value: Any = None
        self._has_return_value: bool = False

    def cancel(self) -> None:
        """Cancel the execution of the original method."""
        if not self.cancellable:
            raise RuntimeError("Cannot cancel a non-cancellable CallbackInfo")
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if execution was cancelled."""
        return self._cancelled

    def set_return_value(self, value: Any) -> None:
        """Set the value to return from the intercepted method."""
        self._return_value = value
        self._has_return_value = True

    def get_return_value(self) -> Any:
        """Retrieve the return value."""
        return self._return_value

    def has_return_value(self) -> bool:
        """Check if a custom return value was provided."""
        return self._has_return_value


def inject(method_name: str, at: str = "HEAD", cancellable: bool = False) -> Callable[..., Any]:
    """Decorator marking a mixin method for injection into a target class."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "_mixin_inject_target", method_name)
        setattr(func, "_mixin_inject_at", at.upper())
        setattr(func, "_mixin_inject_cancellable", cancellable)
        return func
    return decorator


def mixin(target_cls: Type[Any]) -> Callable[[Type[Any]], Type[Any]]:
    """Class decorator that weaves mixin methods into the target class."""
    def class_decorator(mixin_cls: Type[Any]) -> Type[Any]:
        for attr_name in dir(mixin_cls):
            attr_val = getattr(mixin_cls, attr_name)
            if hasattr(attr_val, "_mixin_inject_target"):
                target_method_name = getattr(attr_val, "_mixin_inject_target")
                inject_at = getattr(attr_val, "_mixin_inject_at")
                cancellable = getattr(attr_val, "_mixin_inject_cancellable")
                hook_func = attr_val

                if not hasattr(target_cls, target_method_name):
                    continue

                original_method = getattr(target_cls, target_method_name)

                @functools.wraps(original_method)
                def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                    ci = CallbackInfo(cancellable=cancellable)

                    # Helper to invoke the mixin hook
                    def invoke_hook() -> None:
                        sig = inspect.signature(hook_func)
                        if "ci" in sig.parameters:
                            hook_func(self, *args, ci=ci, **kwargs)
                        else:
                            hook_func(self, *args, **kwargs)

                    if inject_at == "HEAD":
                        invoke_hook()
                        if ci.is_cancelled():
                            return ci.get_return_value() if ci.has_return_value() else None
                        return original_method(self, *args, **kwargs)
                    elif inject_at in ("TAIL", "RETURN"):
                        res = original_method(self, *args, **kwargs)
                        invoke_hook()
                        if ci.has_return_value():
                            return ci.get_return_value()
                        return res
                    else:
                        return original_method(self, *args, **kwargs)

                setattr(target_cls, target_method_name, wrapper)

        return mixin_cls

    return class_decorator
