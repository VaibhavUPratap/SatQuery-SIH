import importlib.util
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / 'experiments' / 'adaptation' / 'train_lora.py'
spec = importlib.util.spec_from_file_location('train_lora_module', module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_normalize_answer() -> None:
    assert module.normalize_answer('  YES  ') == 'yes'
    assert module.normalize_answer('Rural Area') == 'rural area'
    assert module.normalize_answer('  7  ') == '7'


def test_split_train_val_is_deterministic_and_nonempty() -> None:
    records = [{'id': index} for index in range(5)]

    train, validation = module.split_train_val(records, val_ratio=0.2, seed=42)
    repeat_train, repeat_validation = module.split_train_val(records, val_ratio=0.2, seed=42)

    assert train == repeat_train
    assert validation == repeat_validation
    assert len(train) == 4
    assert len(validation) == 1
    assert {item['id'] for item in train}.isdisjoint(item['id'] for item in validation)


def test_split_train_val_rejects_too_small_dataset() -> None:
    try:
        module.split_train_val([{'id': 1}], val_ratio=0.2)
    except ValueError as exc:
        assert 'At least two records' in str(exc)
    else:
        raise AssertionError('Expected a ValueError for a one-record dataset')


def test_resolve_image_path_recovers_relocated_manifest_path(tmp_path: Path) -> None:
    image_path = tmp_path / 'rsvqa_sample_0.png'
    image_path.touch()

    resolved = module.resolve_image_path('/old/machine/rsvqa_sample_0.png', tmp_path / 'train.jsonl')

    assert Path(resolved) == image_path


def test_validate_no_image_overlap_rejects_leakage(tmp_path: Path) -> None:
    train = [{'image': str(tmp_path / 'shared.png')}]
    holdout = [{'image': str(tmp_path / 'shared.png')}]

    try:
        module.validate_no_image_overlap(train, holdout, tmp_path / 'train.jsonl', tmp_path / 'test.jsonl')
    except ValueError as exc:
        assert 'overlaps the holdout' in str(exc)
    else:
        raise AssertionError('Expected image-level overlap to be rejected')


def test_load_training_records_adds_each_manifest_once(tmp_path: Path) -> None:
    base_manifest = tmp_path / 'base.jsonl'
    extra_manifest = tmp_path / 'extra.jsonl'
    base_image = tmp_path / 'base.png'
    extra_image = tmp_path / 'extra.png'
    base_image.touch()
    extra_image.touch()
    base_manifest.write_text('{"image": "base.png", "question": "q", "answer": "yes"}\n')
    extra_manifest.write_text('{"image": "extra.png", "question": "q", "answer": "no"}\n')

    records = module.load_training_records(base_manifest, [extra_manifest])

    assert len(records) == 2
    assert [record['answer'] for record in records] == ['yes', 'no']
