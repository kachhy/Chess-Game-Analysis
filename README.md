# Chess Game Analysis
 A script to analyze and annotate chess games

## How to use
1. You will need a UCI compatible chess engine to analyze your games.
2. Then, obtain the location the file of the game you want to analyze. It should be in PGN format. 
3. To analyze, run the python file with the following arguments. It will print out your average accuracy based on the engine's best moves.
```
python3 analysis.py -p <Path to PGN> -e <Path to engine> -d <engine search depth>
```
4. Finally, the program will create a file called <game>_analyzed.pgn. Upload this file to chess.com's analysis feature, and you should see the move classifications.
5. Rinse and repeat

## Planned features
1. Support for "brilliant" moves
2. MultiPV support
3. New accuracy curve
4. Tweaks and other stuff
