**Tic-Tac-Toe**

This is a Tic-Tac-Toe game implemented in Python.
The game implements a 3x3 board, which can be extended to a larger
size by defining the number of rows and columns in the board creation function.
The game accepts the winning length from the user, and this can also be adjusted
 based on user preference.

I implemented a fix for the issue of overriding an already
filled box by storing already selected combinations into a dictionary.
The game accepts the length to win from the user and implements it by
comparing consecutive combinations from the vertical, horizontal and diagonal tiles.

I assumed that the game is only played once, so I didn't implement scores for user X
and user Y by putting the main function in an endless loop and keeping track of the win
via a scores hash table, with a stop condition to terminate the game and output the final score.

I used Python, Pytest, pipenv and Unittest for mock,
and the used libraries can be installed from the requirements.txt file.

To run the tests, execute the following command:```pytest test_tic_tac_toe.py```
The game can be run from the command line using the following command:```python main.py```
To play the game, enter the row and column numbers to select a box on the board.
The game accepts user input in the format of two numbers separated by a new line.
The rows and columns start from 0.

To play the game, clone unzip the file and navigate to the project directory. Then, run the commands above.

###### **The Tic Tac Toe game implementation has the following features:**
It allows two players to play the game.
The size of the board and the length needed to win can be customized by the players.
The game stops automatically when a player wins or the board is full.
It prevents players from overriding a box that has already been selected.

**The tests provided cover different parts of the game, including:**
_Creating a game board with the correct size and length required to win._
_Updating the board when a player makes a move._
_Checking if there is a horizontal, vertical or diagonal win on the board._
_Printing the current state of the board to the console._
_Getting user input and validating it._
_Checking if there is a win when a custom length is defined._

The tests ensure that the game is implemented correctly and that the different
parts of the game work together as expected. Additionally, by testing the different edge cases,
the code is tested for robustness, and potential errors that might occur during the gameplay are avoided.
