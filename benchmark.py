# Evaluation script for Word Error Rate (WER) benchmarks 
# Used first few lines in harry potter
import jiwer

# 1. Paste the exact human transcript of the speech
ground_truth = ( '''Mr. and Mrs. Dursley live at number 4, Privet
Drive. They are a perfectly normal family. They
do not like anything that is different or strange,
and they hate mysterious things most of all.
They prefer a life that is calm, ordinary and
without any surprises.''')

# 2. Paste your captured outputs
old_output = ""  
new_output = ""  


transformation = jiwer.Compose([
    jiwer.ToLowerCase(),
    jiwer.RemovePunctuation(),
    jiwer.RemoveMultipleSpaces(),
    jiwer.Strip(),
])

# Normalize your texts
clean_truth = transformation(ground_truth)
clean_old = transformation(old_output)
clean_new = transformation(new_output)

# 3. Calculate WER
wer_old = jiwer.wer(clean_truth, clean_old)
wer_new = jiwer.wer(clean_truth, clean_new)

print(f"Old WER: {wer_old * 100:.2f}%")
print(f"New WER: {wer_new * 100:.2f}%")


improvement = ((wer_old - wer_new) / wer_old) * 100
print(f"Accuracy Improvement: {improvement:.2f}%")