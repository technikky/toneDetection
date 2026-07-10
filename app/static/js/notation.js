/** Stage 5: renders offline ABC notation into crisp SVG sheet music via ABCjs. */
function renderNotation(abcString) {
  ABCJS.renderAbc("notation", abcString, {
    responsive: "resize",
    staffwidth: 700,
    paddingtop: 10,
    paddingbottom: 10,
    scale: 1.1,
  });
}
