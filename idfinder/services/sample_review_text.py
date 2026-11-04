"""C18: varied fictional coursework feedback; never used to rewrite genuine reviews."""
from difflib import SequenceMatcher
import random

CONTEXT = (
    'We booked this consultation while planning our home in {place}.',
    'Our family needed a second opinion before committing to the renovation in {place}.',
    'This appointment was for the flat we recently took over at {place}.',
    'I brought measurements and a rough wish list for our place in {place}.',
    'We wanted a realistic starting point for updating our older home in {place}.',
    'After comparing several options, we arranged a discussion about our {place} property.',
    'My partner and I attended the session together to work through our plans for {place}.',
    'The brief concerned a compact home in {place}, with little room for wasted space.',
    'We asked for advice before ordering anything for the apartment at {place}.',
    'I needed help narrowing down the choices for our upcoming move to {place}.',
    'Our main aim was to keep the {place} renovation manageable alongside work.',
    'We were deciding what to retain and what to replace in our home near {place}.',
)
TASK_FACTS = (
    (
        'We discussed whether the sofa would obstruct the route to the bedrooms.',
        'The awkward dining corner was the part of the floor plan we focused on.',
        'I asked about keeping a study area without making the living room feel cramped.',
        'Our measurements included a narrow passage beside the existing built-in cabinets.',
        'The brief included a flexible guest space rather than another permanent partition.',
        'We compared furniture positions with the doors and windows marked on the plan.',
    ),
    (
        'I wanted the sink, hob and preparation counter to work as a sensible sequence.',
        'The main question was how to fit a dishwasher without losing too much storage.',
        'We went through the clearance needed to open drawers beside the refrigerator.',
        'I brought up ventilation and the position of the washing area near the service yard.',
        'The discussion centred on using the corner cabinets without blocking the entrance.',
        'Our existing kitchen had very little preparation space between the appliances.',
    ),
    (
        'We compared floor finishes that would be easier to maintain with a pet at home.',
        'The choices included cabinet laminates that would work with our existing tiles.',
        'I asked about textured wall finishes and how difficult they would be to clean.',
        'Our priority was finding a countertop that suited daily cooking rather than a show kitchen.',
        'We looked at the difference between the samples under daylight and warmer lighting.',
        'The material discussion covered moisture resistance near the bathroom entrance.',
    ),
    (
        'The darker corridor needed a different lighting approach from the living area.',
        'I wanted separate lighting for reading at night and hosting friends at weekends.',
        'We checked where glare might appear on the television and work monitor.',
        'The brief was to avoid a ceiling full of downlights in a relatively small room.',
        'Our questions were about switches, bedside lights and the route to the bathroom.',
        'We considered how the lighting would look with our planned wall and floor colours.',
    ),
    (
        'We needed to understand which decisions had to be made before requesting quotations.',
        'I asked which works could wait until later without requiring the same areas to be redone.',
        'The discussion covered the order of wet works, carpentry and final installation.',
        'We compared the cost implications of keeping the existing flooring or replacing it.',
        'Our timeline had to allow for a move-out date and deliveries from several suppliers.',
        'I wanted a clearer boundary between essential repairs and optional decorative work.',
    ),
    (
        'The entrance needed room for shoes without narrowing the walkway.',
        'We asked about storing luggage above the wardrobes while keeping everyday items accessible.',
        'Our household has sports equipment that did not fit neatly into the original cabinets.',
        'I needed a place for cleaning supplies away from the cooking and dining areas.',
        'The brief included books, a printer and work documents in a shared study corner.',
        'We discussed how to add storage around an existing structural column.',
    ),
)
PROCESS = (
    'I shared photographs of the existing rooms before the meeting.',
    'We used the session to compare two options rather than settle every detail.',
    'A short written brief helped us explain which items we were keeping.',
    'I had a few reference pictures, but was open to a different approach.',
    'We checked the proposal against the dimensions we had taken ourselves.',
    'The conversation also covered how the room would be used on an ordinary weekday.',
    'We brought a list of questions gathered during our first viewing of the property.',
    'There were some existing fittings that we intended to retain for practical reasons.',
    'My partner was more concerned about maintenance, while I focused on the layout.',
    'We had a spending limit and wanted to understand the trade-offs before proceeding.',
    'I asked for an explanation of the assumptions behind the initial suggestions.',
    'We were still at the planning stage, so the scope was advice rather than construction.',
)
OUTCOMES = {
    5: (
        'The designer was excellent at turning those concerns into clear, practical next steps.',
        'Everything was explained patiently and the follow-up notes were genuinely useful.',
        'The advice was thoughtful, specific to our brief and delivered when promised.',
        'We left feeling confident about the next stage and very satisfied with the service.',
        'The proposed solution was creative without ignoring the limits of the space.',
        'Communication was responsive throughout and our questions received detailed answers.',
        'The revised plan resolved our main concern and stayed within the agreed scope.',
        'I appreciated the professional preparation and would happily work with this designer again.',
    ),
    4: (
        'The suggestions were helpful overall, although one small detail needed a second explanation.',
        'We received good advice; the follow-up took slightly longer than we had expected.',
        'The session gave us a useful direction, with a few measurements still to confirm.',
        'The designer handled our questions well, but I would have liked a little more time on costs.',
        'Most of the proposal suited our needs and we asked for one modest adjustment.',
        'The work was practical and clearly presented, with a minor omission in the notes.',
        'We were pleased with the overall approach even though the appointment started a little late.',
        'The discussion was worthwhile; a broader comparison of alternatives would have made it even better.',
    ),
    3: (
        'Some suggestions were usable, but the proposal still needed clarification before we could decide.',
        'The session covered the basics without fully resolving the concern we had raised.',
        'We received a workable starting point, although it felt less tailored than we expected.',
        'A few ideas helped, while other parts repeated options we had already considered.',
        'The result was acceptable for an initial discussion, with several questions left open.',
        'We needed another conversation to connect the recommendations to our actual measurements.',
        'The notes arrived, but some of the reasoning behind the choices was missing.',
        'It was a mixed experience: useful context, but not enough detail for the next decision.',
    ),
    2: (
        'The response was late and did not deal adequately with the specific problem in our brief.',
        'I had to chase updates and the revised suggestion still overlooked an important constraint.',
        'The advice stayed too general despite the measurements and photographs we supplied.',
        'Communication was poor and we were left to work out several practical details ourselves.',
        'The follow-up missed our agreed deadline and repeated a point we had already corrected.',
        'We were disappointed by the lack of preparation for the questions sent in advance.',
        'The proposal required substantial rework before it could be useful to us.',
        'Too many assumptions were made without checking what we had asked for.',
    ),
    1: (
        'Repeated missed follow-ups and poor communication made this a very frustrating experience.',
        'The delivered advice ignored the main requirement, even after we had explained it twice.',
        'We received no usable resolution to the issue that the appointment was meant to address.',
        'The agreed revision never arrived, and our attempts to obtain an update went unanswered.',
        'The proposal was inconsistent with the supplied measurements and was not corrected as promised.',
        'We were very disappointed by the service and would not continue with this arrangement.',
        'There were repeated delays without a clear explanation or a satisfactory follow-up.',
        'The session and its follow-up fell well short of the scope that had been agreed.',
    ),
}


def _similar(first, second):
    a, b = ' '.join(first.lower().split()), ' '.join(second.lower().split())
    words_a, words_b = set(a.split()), set(b.split())
    if len(words_a & words_b) < .4 * len(words_a | words_b):
        return False
    matcher = SequenceMatcher(None, a, b)
    return matcher.real_quick_ratio() >= .85 and matcher.quick_ratio() >= .85 and matcher.ratio() >= .85


def sample_comment(key, rating, task, place, existing=()):
    """Build a varied, specific sample without recycling another sample's paragraph.

    Integrity thresholds and checks for actual customer reviews remain unchanged.
    """
    rng = random.Random(str(key) + ':review-text-v2')
    for _ in range(1000):
        sentences = [rng.choice(CONTEXT).format(place=place), rng.choice(TASK_FACTS[task]),
                     rng.choice(PROCESS), rng.choice(OUTCOMES[rating])]
        comment = ' '.join(sentences)
        if not any(_similar(comment, other) for other in existing if other):
            return comment
    raise ValueError('Could not prepare distinct sample feedback; no data was overwritten.')
