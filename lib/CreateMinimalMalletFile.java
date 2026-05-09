import cc.mallet.pipe.Pipe;
import cc.mallet.types.InstanceList;
import java.io.File;

public class CreateMinimalMalletFile {
    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            System.err.println(
                "Usage: CreateMinimalMalletFile <original-instance-list-file> <minimal-instance-list-file>"
            );
            System.exit(1);
        }

        String originalFile = args[0];
        String minimalFile = args[1];

        InstanceList originalInstances = InstanceList.load(new File(originalFile));
        Pipe pipe = originalInstances.getPipe();
        InstanceList minimalInstances = new InstanceList(pipe);

        if (originalInstances.size() > 0) {
            minimalInstances.add(originalInstances.get(0));
        }

        minimalInstances.save(new File(minimalFile));
    }
}
