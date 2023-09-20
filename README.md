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

# About Single Game Performance/Elo Estimation (SGP)
This is a very WIP feature that allows for the estimation of game performance purely by accuracy against a the computer.
Assuming that you are analyzing with a strong engine, the maximum "Elo" should be around 3500-3600 with 100% accuracy.
This is not a measure of the rating that you are on any platform/OTB organization in any way. This is simply how well you performed relative to your opponent in a single game.
As of now, this model is generated from ~16.6m Lichess games ([Lichess Database](https://database.lichess.org)) across many rating levels. In the future, I intend to add more factors, such as number of blunders and mistakes to determine a better performance rating (for example if you accidentally blunder mate in 1 in a game that you were playing well in before).
This feature is in no way based upon the rating present in the original PGN. 

## Planned features
1. Support for "brilliant" moves
2. MultiPV support
3. Improved game performance rating
4. Tweaks and other stuff
5. Support for multi game PGNs
