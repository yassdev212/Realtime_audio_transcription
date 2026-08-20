# Evaluation script for Word Error Rate (WER) benchmarks 
# Used first few lines in harry potter
import jiwer

# 1. Paste the exact human transcript of the speech
ground_truth = ( '''The birch canoe slid on the smooth planks.
Glue the sheet to the dark blue background.
It's easy to tell the depth of a well.
These days a chicken leg is a rare dish.
Rice is often served in round bowls.
The juice of lemons make fine punch.
The box was thrown beside the parked truck.
The hogs were fed corn and garbage.
Four hours of steady work faced us.
A large size in stockings is hard to sell.''')

# 2. Paste your captured outputs
output = "he Burke Canoe slid on the smooth. 2 planks. Glue the sheet to the dark background. It's easy to tell the depth of a well. These days a chicken leg is A bear dish. Rice is often served in round bowl. The juice of lemons make fine. A The box was thrown beside the parked truck. The hogs were fed corn and Garbage. Four hours of steady work faced us. A large size in stockings is hard to sell."  
 


transformation = jiwer.Compose([
    jiwer.ToLowerCase(),
    jiwer.RemovePunctuation(),
    jiwer.RemoveMultipleSpaces(),
    jiwer.Strip(),
])

# Normalize your texts
clean_truth = transformation(ground_truth)
clean_output = transformation(output)


# 3. Calculate WER
wer = jiwer.wer(clean_truth, clean_output)


print(f"WER: {wer * 100:.2f}%")



