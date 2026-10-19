"""One background preparation pass, reporting truthful file/stage progress."""
from dataclasses import dataclass
from pathlib import Path
import time


@dataclass(frozen=True)
class Source:
    path: Path
    name: str
    origin: str = ""
    archive: Path | None = None


def prepare_batch(paths, archives, converter, events, cancel):
    """Never touch Tk or the library from this worker."""
    def emit(kind, **values):
        events.put({"kind": kind, **values})
    sources = []
    errors = []
    completed = 0
    ready = 0
    started = time.monotonic()
    try:
        for path in paths:
            if cancel.is_set():
                break
            if path.suffix.lower() == ".zip":
                def extraction(stage, detail="", fraction=None, name=path.name):
                    if cancel.is_set():
                        raise InterruptedError("Import canceled")
                    emit("archive", path=path, name=name, stage=stage, detail=detail, fraction=fraction)
                try:
                    extraction("Checking archive", "Finding PDF and PowerPoint files")
                    imported = archives.extract(path, progress=extraction)
                    sources.extend(Source(entry.path, entry.name, entry.source, entry.archive) for entry in imported)
                    emit("archive_done", path=path, name=path.name, detail=f"Found {len(imported)} document(s)")
                except InterruptedError:
                    break
                except Exception as error:
                    errors.append(f"{path.name}: {error}")
                    converter.logger.exception("ZIP import failed: %s", path)
                    emit("archive_error", path=path, name=path.name, detail=str(error))
            else:
                sources.append(Source(path, path.name))
        emit("discovered", sources=sources)
        for index, source in enumerate(sources):
            if cancel.is_set():
                break
            def progress(stage, detail="", fraction=None):
                converter.logger.debug("Import stage: %s | %s | %s", source.name, stage, detail)
                emit("stage", path=source.path, name=source.name, stage=stage, detail=detail,
                     completed=completed, total=len(sources))
            try:
                progress("Reading file", "Checking document")
                result = converter.prepare(source.path, progress=progress)
                ready += 1
                emit("ready", path=source.path, result=result)
            except Exception as error:
                errors.append(f"{source.name}: {error}")
                converter.logger.exception("Document preparation failed: %s", source.name)
                emit("error", path=source.path, detail=str(error))
            completed = index + 1
            emit("count", completed=completed, total=len(sources), ready=ready, failed=len(errors))
    except Exception as error:
        converter.logger.exception("Import batch failed")
        errors.append(str(error))
    finally:
        emit("done", completed=completed, total=len(sources), ready=ready, errors=errors,
             canceled=cancel.is_set(), elapsed=time.monotonic() - started)
