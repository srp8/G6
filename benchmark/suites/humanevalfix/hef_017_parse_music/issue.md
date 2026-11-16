# Bug: `parse_music` returns wrong results

`parse_music(music_string: str) -> List[int]` in `parse_music.py` is supposed to do the following:

> Input to this function is a string representing musical notes in a special ASCII format.
> Your task is to parse this string and return list of integers corresponding to how many beats does each
> not last.
> Here is a legend:
> 'o' - whole note, lasts four beats
> 'o|' - half note, lasts two beats
> '.|' - quater note, lasts one beat
> >>> parse_music('o o| .| o| o| .| .| .| .| o o')
> [4, 2, 1, 2, 2, 1, 1, 1, 1, 4, 4]

The unit tests in `tests/` fail. Find and fix the bug in `parse_music.py` so that all tests pass. Do not modify the tests.
