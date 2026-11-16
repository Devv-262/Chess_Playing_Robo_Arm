# Model comparison on held-out, hand-checked photos

- wired-in model: `data/yolo/best.pt`
- candidate: `data/yolo/candidate/best.pt`
- photos: 33 (never used for training either model)
- conf 0.35, IoU 0.5. 'perfect photo' = every piece boxed with the right class, nothing extra, nothing missing.

## Inference size 960

| lighting | wired F1 | candidate F1 | wired perfect photos | candidate perfect photos |
|---|---|---|---|---|
| plain | 0.909 | 0.985 | 16/33 | 27/33 |
| dull yellow | 0.895 | 0.986 | 16/33 | 27/33 |
| warm yellow | 0.904 | 0.986 | 16/33 | 27/33 |
| bright white | 0.897 | 0.985 | 16/33 | 27/33 |
| cool white | 0.904 | 0.986 | 15/33 | 27/33 |
| overexposed | 0.847 | 0.986 | 13/33 | 27/33 |
| dim | 0.897 | 0.986 | 14/33 | 28/33 |

## Inference size 1280

| lighting | wired F1 | candidate F1 | wired perfect photos | candidate perfect photos |
|---|---|---|---|---|
| plain | 0.936 | 0.994 | 16/33 | 29/33 |
| dull yellow | 0.927 | 0.994 | 16/33 | 29/33 |
| warm yellow | 0.942 | 0.992 | 17/33 | 29/33 |
| bright white | 0.930 | 0.992 | 17/33 | 29/33 |
| cool white | 0.935 | 0.994 | 17/33 | 29/33 |
| overexposed | 0.867 | 0.994 | 13/33 | 29/33 |
| dim | 0.885 | 0.994 | 11/33 | 29/33 |

## Inference size 1920

| lighting | wired F1 | candidate F1 | wired perfect photos | candidate perfect photos |
|---|---|---|---|---|
| plain | 0.553 | 0.985 | 10/33 | 26/33 |
| dull yellow | 0.536 | 0.984 | 11/33 | 25/33 |
| warm yellow | 0.535 | 0.985 | 9/33 | 25/33 |
| bright white | 0.544 | 0.984 | 11/33 | 24/33 |
| cool white | 0.570 | 0.985 | 12/33 | 26/33 |
| overexposed | 0.484 | 0.982 | 10/33 | 24/33 |
| dim | 0.518 | 0.986 | 10/33 | 26/33 |

## Per piece type (plain photos, inference size 1280)

| piece | wired P | wired R | wired F1 | candidate P | candidate R | candidate F1 | boxes in truth |
|---|---|---|---|---|---|---|---|
| P | 0.95 | 0.99 | 0.97 | 0.99 | 1.00 | 1.00 | 114 |
| N | 0.81 | 0.92 | 0.86 | 1.00 | 1.00 | 1.00 | 24 |
| B | 0.85 | 0.90 | 0.88 | 1.00 | 0.97 | 0.98 | 31 |
| R | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 28 |
| Q | 0.70 | 1.00 | 0.82 | 1.00 | 1.00 | 1.00 | 14 |
| K | 1.00 | 0.72 | 0.84 | 1.00 | 1.00 | 1.00 | 18 |
| p | 0.97 | 0.94 | 0.95 | 0.96 | 1.00 | 0.98 | 67 |
| n | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 22 |
| b | 1.00 | 0.92 | 0.96 | 1.00 | 1.00 | 1.00 | 26 |
| r | 0.86 | 1.00 | 0.92 | 1.00 | 1.00 | 1.00 | 24 |
| q | 1.00 | 0.67 | 0.80 | 1.00 | 1.00 | 1.00 | 12 |
| k | 0.87 | 1.00 | 0.93 | 1.00 | 1.00 | 1.00 | 13 |
